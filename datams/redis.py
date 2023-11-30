from io import StringIO
import pandas as pd
from flask import Flask, current_app, g
from redis import Redis
from typing import Union  # , Optional
from datams.utils import APP_CONFIG, REMOVE_STALES_EVERY
import datetime as dt
import time


import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


ALIVE_RETRY_INTERVAL = 0.05  # seconds
ALIVE_LOCK_EXPIRY = 10  # this should only comes into play if a thread crashes

# TODO: Consider adding locks to other set methods
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


# TODO: Consider emitting a signal when processed_files or pending_files are set to let
#       application know they are ready
def set_processed_files(df: Union[pd.DataFrame, str]) -> None:
    df = df.to_json() if type(df) is pd.DataFrame else df
    redis = get_redis()
    redis.set('processed_files', df)


def get_processed_files() -> pd.DataFrame:
    redis = get_redis()
    df = redis.get('processed_files')
    empty = pd.DataFrame(columns=['id', 'level', 'owner', 'description', 'filename',
                                  'uploaded', 'url'])
    return empty if df is None else pd.read_json(StringIO(df))


# TODO: Uncomment if calls to extract this data is too slow
# def set_pending_files(df: Union[pd.DataFrame, str]) -> None:
#     df = df.to_json() if type(df) is pd.DataFrame else df
#     redis = get_redis()
#     redis.set('pending_files', df)
#
#
# def get_pending_files() -> pd.DataFrame:
#     redis = get_redis()
#     df = redis.get('pending_files')
#     empty = pd.DataFrame(columns=['file', 'last_modified'])
#     return empty if df is None else pd.read_json(StringIO(df))
#
#
def set_discovered_files(df: Union[pd.DataFrame, str]) -> None:
    df = df.to_json() if type(df) is pd.DataFrame else df
    redis = get_redis()
    redis.set('discovered_files', df)


def get_discovered_files() -> pd.DataFrame:
    redis = get_redis()
    df = redis.get('discovered_files')
    empty = pd.DataFrame(columns=['file', 'last_modified'])
    return empty if df is None else pd.read_json(StringIO(df))


def get_alive() -> pd.DataFrame:
    redis = get_redis()
    alive = redis.get('alive')
    alive = [] if alive is None else eval(alive)  # convert from str to list
    return alive


# TODO: Consider renaming this append or push to alive instead.
#       Consider using redis list type instead
def set_alive(value):
    """
    If reset is True and value is not None then the list is reset before appending the
    value.
    """
    upload_id, timestamp = value
    redis = get_redis()
    locked = True if redis.exists('alive_lock') == 1 else False
    while True:
        if locked:
            time.sleep(ALIVE_RETRY_INTERVAL)
        else:
            # 1. set the lock
            redis.set('alive_lock', 'y', dt.timedelta(seconds=ALIVE_LOCK_EXPIRY))
            now = dt.datetime.now().timestamp()
            alive = get_alive()
            alive = [(uid, ts) for uid, ts in alive if uid != upload_id and
                     (now - ts) < REMOVE_STALES_EVERY]  # remove old entries
            alive.append(value)  # append the value
            redis.set('alive', str(alive))
            # 2. release the lock
            redis.delete('alive_lock')
            break


def redis_init_app(app: Flask) -> Redis:
    redis = Redis(**app.config['REDIS'])
    app.extensions['redis'] = redis
    return redis
