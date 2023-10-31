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


# TODO: Consider emitting a signal when dfiles set to let application know the result is
#       ready
def set_files(dfiles: Union[pd.DataFrame, str]) -> None:
    dfiles = dfiles.to_json() if type(dfiles) is pd.DataFrame else dfiles
    redis = get_redis()
    redis.set('dfiles', dfiles)


def get_files() -> pd.DataFrame:
    redis = get_redis()
    dfiles = redis.get('dfiles')
    empty = pd.DataFrame(columns=['id', 'level', 'owner', 'description', 'filename',
                                  'uploaded', 'url'])
    return empty if dfiles is None else pd.read_json(StringIO(dfiles))


def redis_init_app(app: Flask) -> Redis:
    redis = Redis(**app.config['REDIS'])
    app.extensions['redis'] = redis
    return redis
