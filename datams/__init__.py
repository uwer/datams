import os
import sys

from datams.flask import flask_init_app
from datams.celery import celery_init_app
from datams.flask_login import flask_login_init_app
from datams.redis import redis_init_app
from datams.db import database_init_app

# add this package to path to allow absolute imports
sys.path.append(os.path.dirname(os.path.realpath(__file__)))


def create_app(test_config=None):
    """
    This method represents an application factory.

    The name of this method is automatically recognized by flask and will be executed
    when flask is directed to this directory.
    """
    # 1) initialize and configure flask app
    app = flask_init_app(__name__, test_config)

    # 2) initialize database and upload directories
    database_init_app(app)

    # 3) initialize redis server for caching
    redis_init_app(app)

    # 4) initialize celery_app for running background tasks
    celery_init_app(app)
    # app.extensions['celery'] = celery_app

    # 5) initialize the login manager
    flask_login_init_app(app)

    return app

