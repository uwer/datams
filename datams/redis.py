from io import StringIO
import pandas as pd
from flask import Flask, current_app, g
from redis import Redis
from typing import Any
from datams.utils import APP_CONFIG
import datetime as dt
import time
import functools


# interval between attempts to acquire lock
RETRY_INTERVAL = dict(checkins=0.05, default=0.05)  # seconds
# should only be relevant thread crashes
LOCK_EXPIRY = dict(checkins=10, default=60)  # seconds


# NOTE: not the first argument of any methods decorated by this method should be `key`
#       this determines which lock to use
# TODO: Implement the locking in a better more robust manner
# TODO: Implement require lock to be used with the `with` statement to ensure the lock
#       is released
# TODO: Add ability to have multiple locks, but beware of dead-locking
def requires_lock(_func=None, *, unused_arg=None):
    def decorator_requires_lock(func):
        @functools.wraps(func)
        def wrapper_requires_lock(key, *args, **kwargs):
            acquire_lock(key)
            retval = func(key, *args, **kwargs)
            release_lock(key)
            return retval
        return wrapper_requires_lock
    if _func is None:
        return decorator_requires_lock
    else:
        return decorator_requires_lock(_func)


def get_redis(app: Flask = None) -> Redis:
    try:
        if app is None:
            if 'redis' not in g:
                g.redis = current_app.extensions['redis']
            return g.redis
        else:
            return app.extensions['redis']
    except RuntimeError:
        return Redis(**APP_CONFIG['REDIS'])


def is_locked(key: str):
    # return True if key is locked otherwise return False
    redis = get_redis()
    return True if redis.exists(f"{key}_lock") == 1 else False


def is_working(key: str):
    # return False if key exists otherwise return True
    redis = get_redis()
    return True if redis.exists(f"{key}_working") == 1 else False


def set_working(key: str):
    redis = get_redis()
    redis.set(f"{key}_working", 'y')
    return


def set_finished(key: str):
    delete_key(f"{key}_working")
    return


def acquire_lock(key: str):
    retry_interval = RETRY_INTERVAL.get(key, RETRY_INTERVAL['default'])
    lock_expiry = LOCK_EXPIRY.get(key, LOCK_EXPIRY['default'])
    redis = get_redis()
    while True:
        locked = True if redis.exists(f"{key}_lock") == 1 else False
        if locked:
            time.sleep(retry_interval)
        else:
            # 1. set the lock
            redis.set(f"{key}_lock", 'y', dt.timedelta(seconds=lock_expiry))
            break
    return


def release_lock(key: str):
    delete_key(f"{key}_lock")


def delete_key(key: str):
    redis = get_redis()
    if redis.exists(key) == 1:
        redis.delete(key)
    return


@requires_lock
def set_value(key, value) -> None:
    # locking is preformed within the celery tasks that call this method
    # it is assumed that caller has acquired the lock before calling this method
    redis = get_redis()
    redis.set(key, value)


def get_value(key: str) -> Any:
    redis = get_redis()
    key_conversion_default = dict(
        processed_files=(
            lambda x: pd.read_json(StringIO(x)),
            pd.DataFrame(columns=['id', 'level', 'owner', 'description', 'filename',
                                  'uploaded', 'url'])
        ),
        pending_files=(
            lambda x: pd.read_json(StringIO(x)),
            pd.DataFrame(columns=['id', 'filename', 'uploaded', 'uploaded_by'])
        ),
        discovered_files=(
            lambda x: pd.read_json(StringIO(x)),
            pd.DataFrame(columns=['id', 'filename', 'last_modified'])
        ),
        deleted_files=(
            lambda x: pd.read_json(StringIO(x)),
            pd.DataFrame(columns=['id', 'filename', 'description', 'uploaded',
                                  'deleted', 'original_id', 'ftype'])
        ),
        checkins=(eval, []),
    )
    is_vkey = False
    if key.startswith('vkey_'):
        is_vkey = True
        root_key = '_'.join(key.split('_')[2:])
    else:
        root_key = key
    if root_key not in key_conversion_default.keys():
        raise RuntimeError(f"Attempting to get unknown key: `{root_key}`")
    conversion, default = key_conversion_default[root_key]
    value = redis.get(key)
    if is_vkey and value is None:
        root_value = redis.get(root_key)
        root_value = default.to_json() if root_value is None else root_value
        set_value(key, root_value)
        value = root_value
    return default if value is None else conversion(value)


# TODO: Consider expanding this concept to any variables we want to freeze for a view so
#       that removing these would simply entail looking for a specific key prefix and
#       seeing if the uploads_id is valid rather than explicitly listing each type.
def remove_stale_vkeys(valid_uids):
    redis = get_redis()
    delete = [k for k in redis.scan_iter("vkey_*") if k.split('_')[1] not in valid_uids]
    for k in delete:
        redis.delete(k)


def redis_init_app(app: Flask) -> Redis:
    redis = Redis(**app.config['REDIS'])
    app.extensions['redis'] = redis
    return redis
