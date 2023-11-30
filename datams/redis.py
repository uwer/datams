from io import StringIO
import pandas as pd
from flask import Flask, current_app, g
from redis import Redis
from typing import Union, Any
from datams.utils import APP_CONFIG, REMOVE_STALES_EVERY
import datetime as dt
import time


import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)

# interval between attempts to acquire lock
RETRY_INTERVAL = dict(checkins=0.05, default=0.05)  # seconds
# should only be relevant thread crashes
LOCK_EXPIRY = dict(checkins=10, default=60)  # seconds


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
    redis = get_redis()
    if redis.exists(f"{key}_lock") == 1:
        redis.delete(f"{key}_lock")
    return


def set_value(key, value) -> None:
    # locking is preformed within the celery tasks that call this method
    # it is assumed that caller has acquired the lock before calling this method
    redis = get_redis()
    redis.set(key, value)


def get_value(key) -> Any:
    redis = get_redis()
    key_conversion_default = dict(
        processed_files=(lambda x: pd.read_json(StringIO(x)),
                         pd.DataFrame(columns=['id', 'level', 'owner', 'description',
                                               'filename', 'uploaded', 'url'])),
        discovered_files=(lambda x: pd.read_json(StringIO(x)),
                          pd.DataFrame(columns=['filename', 'last_modified'])),
        checkins=(eval, []),
        pending_files=(lambda x: pd.read_json(StringIO(x)),
                       pd.DataFrame(columns=['filename', 'uploaded', 'uploaded_by'])),
        deleted_files=(lambda x: pd.read_json(StringIO(x)),
                       pd.DataFrame(columns=['filename', 'deleted', 'deleted_by',
                                             'originally_uploaded_by']))
    )
    if key not in key_conversion_default.keys():
        raise RuntimeError(f"Attempting to get unknown key: `{key}`")
    conversion, default = key_conversion_default[key]
    value = redis.get(key)
    return default if value is None else conversion(value)


def redis_init_app(app: Flask) -> Redis:
    redis = Redis(**app.config['REDIS'])
    app.extensions['redis'] = redis
    return redis
