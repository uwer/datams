import os
import datetime as dt
from flask import Flask
from celery import Celery, Task, shared_task
from datams.redis import set_processed_files, set_discovered_files, get_alive
from datams.db.queries.select import select_files, select_discovered_files
from datams.utils import PENDING_DIRECTORY, REMOVE_STALES_EVERY


# define background tasks
# TODO: Consider renaming this compute_processed_files_task
@shared_task(ignore_result=False)
def get_processed_files_task():
    df = select_files('file.root')
    return df.to_json()


@shared_task
def set_processed_files_task(result):
    set_processed_files(result)


# TODO: Consider renaming this compute_discovered_files_task
@shared_task(ignore_result=False)
def get_discovered_files_task():
    df = select_discovered_files()
    return df.to_json()


@shared_task
def set_discovered_files_task(result):
    set_discovered_files(result)


@shared_task
def remove_stales_task():
    now = dt.datetime.now().timestamp()
    alive = get_alive()
    alive = [a[0] for a in alive if (now - a[1]) < REMOVE_STALES_EVERY]
    temp_files = [f for f in os.listdir(PENDING_DIRECTORY)
                  if (os.path.isfile(f"{PENDING_DIRECTORY}/{f}") and
                      f.startswith('.temp'))]
    to_remove = [f"{PENDING_DIRECTORY}/{f}" for f in temp_files
                 if '.'.join(f[6:].split('.')[:2]) not in alive]
    for f in to_remove:
        os.remove(f)


# TODO: Uncomment if these should be implemented as background tasks
# @shared_task(ignore_result=False)
# def get_pending_files_task(pending_directory):
#     data = [(str(f), dt.datetime.fromtimestamp(os.path.getmtime(f))) for f in
#             Path(pending_directory).rglob('*') if f.is_file()]
#     files = [f for f, _ in data]
#     last_modifies = [mt for _, mt in data]
#     return pd.DataFrame({'file': files, 'last_modified': last_modifies}).to_json()
#
#
# @shared_task
# def set_pending_files_task(result):
#     set_pending_files(result)
#
#
# def load_pending_files(pending_directory):
#     # chain the tasks together so result is piped to the next task
#     chain = get_pending_files_task.s(pending_directory) | set_pending_files_task.s()
#     chain()
#
#

def load_processed_files():
    # chain the tasks together so result is piped to the next task
    chain = get_processed_files_task.s() | set_processed_files_task.s()
    chain()


def load_discovered_files():
    # chain the tasks together so result is piped to the next task
    chain = (get_discovered_files_task.s() | set_discovered_files_task.s())
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

    # 4) start background task of discovering files
    load_discovered_files()

    # 5) start period task of removing stale files
    celery_app.conf.beat_schedule = {
        'remove_stale_pending_files': {
            'task': 'datams.celery.remove_stales_task',
            'schedule': app.config['DATA_FILES']['remove_stales_every'],
            # 'args': (PENDING_DIRECTORY,)
        },
    }

    # 6) start background task of loading pending files
    # load_pending_files(f"{app.config['DATA_FILES']['upload_directory']}/pending")

    # TODO: Follow similar pattern for loading deleted files?
    # 7) start background task of loading pending files
    # load_pending_files(f"{app.config['DATA_FILES']['upload_directory']}/pending")

    return celery_app
