from io import StringIO
import pandas as pd
from flask import Flask, current_app, g
from redis import Redis
from typing import Union  # , Optional
from datams.utils import APP_CONFIG

import logging
logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.DEBUG)


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


# TODO: Implement pending files and discovered files as pandas dataframes
def set_pending_files(df: Union[pd.DataFrame, str]) -> None:
    df = df.to_json() if type(df) is pd.DataFrame else df
    redis = get_redis()
    redis.set('pending_files', df)


def get_pending_files() -> pd.DataFrame:
    redis = get_redis()
    df = redis.get('pending_files')
    empty = pd.DataFrame(columns=['file', 'last_modified'])
    return empty if df is None else pd.read_json(StringIO(df))


def set_discovered_files(df: Union[pd.DataFrame, str]) -> None:
    df = df.to_json() if type(df) is pd.DataFrame else df
    redis = get_redis()
    redis.set('discovered_files', df)


def get_discovered_files() -> pd.DataFrame:
    redis = get_redis()
    df = redis.get('discovered_files')
    empty = pd.DataFrame(columns=['file', 'last_modified'])
    return empty if df is None else pd.read_json(StringIO(df))


def redis_init_app(app: Flask) -> Redis:
    redis = Redis(**app.config['REDIS'])
    app.extensions['redis'] = redis
    return redis
