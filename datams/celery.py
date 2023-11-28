import os
import datetime as dt
from pathlib import Path

import pandas as pd
from flask import Flask
from celery import Celery, Task, shared_task
from datams.redis import set_processed_files, set_pending_files, set_discovered_files
from datams.db.queries.select import select_files


# define background tasks
@shared_task(ignore_result=False)
def get_processed_files_task():
    df = select_files('file.root')
    return df.to_json()


@shared_task
def set_processed_files_task(result):
    set_processed_files(result)


def load_processed_files():
    # chain the tasks together so result is piped to the next task
    chain = get_processed_files_task.s() | set_processed_files_task.s()
    chain()


# TODO: This may not be too slow and therefore could possibly be preformed as needed.
@shared_task(ignore_result=False)
def get_pending_files_task(pending_directory):
    data = [(str(f), dt.datetime.fromtimestamp(os.path.getmtime(f))) for f in
            Path(pending_directory).rglob('*') if f.is_file()]
    files = [f for f, _ in data]
    last_modifies = [mt for _, mt in data]
    return pd.DataFrame({'file': files, 'last_modified': last_modifies}).to_json()


@shared_task
def set_pending_files_task(result):
    set_pending_files(result)


def load_pending_files(pending_directory):
    # chain the tasks together so result is piped to the next task
    chain = get_pending_files_task.s(pending_directory) | set_pending_files_task.s()
    chain()


@shared_task(ignore_result=False)
def get_discovered_files_task(discovery_directory):
    # TODO: Turn this into a dataframe with the columns we want
    touched_files = []
    normal_files = set([
        str(f) if not str(f).endswith('.touch') else touched_files.append(str(f)[:-6])
        for f in Path(discovery_directory).rglob('*')
        if f.is_file()
    ])
    if None in normal_files:
        normal_files.remove(None)
    files = sorted(list(normal_files.difference(touched_files)))
    last_modifies = [dt.datetime.fromtimestamp(os.path.getmtime(f)) for f in files]
    return pd.DataFrame({'file': files, 'last_modified': last_modifies}).to_json()


@shared_task
def set_discovered_files_task(result):
    set_discovered_files(result)


def load_discovered_files(discovery_directory):
    # chain the tasks together so result is piped to the next task
    chain = (get_discovered_files_task.s(discovery_directory) |
             set_discovered_files_task.s())
    chain()


def celery_init_app(app: Flask) -> Celery:
    # 1) define flask/celery task object to share context variables
    class FlaskTask(Task):
        def __call__(self, *args: object, **kwargs: object) -> object:
            with app.app_context():
                return self.run(*args, **kwargs)

    # 2) initialize and configure the celery app
    celery_app = Celery(app.name)  # include=('datams.redis',)
    celery_app.config_from_object(app.config['CELERY'])
    celery_app.Task = FlaskTask
    celery_app.set_default()
    app.extensions['celery'] = celery_app

    # 3) start background task of loading processed files
    load_processed_files()

    # 4) start background task of loading pending files
    load_pending_files(f"{app.config['DATA_FILES']['upload_directory']}/pending")

    # 5) start background task of discovering files
    load_discovered_files(app.config['DATA_FILES']['discovery_directory'])

    # TODO: Follow similar pattern for loading deleted files?

    return celery_app
