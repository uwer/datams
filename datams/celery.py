from typing import Tuple
from flask import Flask
from celery import Celery, Task, shared_task

from datams.redis import get_value, set_value, acquire_lock, release_lock, is_locked
from datams.utils import remove_stale_files, update_and_append_to_checkins
from datams.db.queries.select import select_query

#  Note in order to know if value is ready application can check if the
#  `<key>_lock` key exists.  If it doesn't then it should be ready.  Otherwise
#  it is currently being computed and set


def requires_lock(function, ignore_when_locked=False):
    def wrapper(*args, lock=None, **kwargs):
        if lock is None:
            raise RuntimeError('Lock key required')
        if not ignore_when_locked or not is_locked(lock):
            acquire_lock(lock)
            function(*args, **kwargs)
            release_lock(lock)
    return wrapper


# define background tasks
@shared_task
@requires_lock(ignore_when_locked=True)
def compute_and_set_task(key) -> None:
    # FIXME: Currently this method assumes all data coming from select_query is a pandas
    #        Dataframe.
    try:
        # if key is not implemented, release the lock and ignore the request
        value = select_query(data=key).to_json()
        set_value(key, value)
    except NotImplementedError:
        pass


@shared_task
@requires_lock
def update_checkins(value: Tuple[str, float]) -> None:
    checkins = get_value('checkins')
    updated_checkins = update_and_append_to_checkins(checkins, value)
    set_value(checkins, str(updated_checkins))


@shared_task
@requires_lock
def remove_stale_files_task() -> None:
    checkins = get_value('checkins')
    remove_stale_files(checkins)


def task_complete(key) -> bool:
    return False if is_locked(key) else True


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

    # 3) start background task of computing and setting processed files
    compute_and_set_task.delay('processed_files', lock='processed_files')

    # 4) start background task of discovering files
    compute_and_set_task.delay('discovered_files', lock='discovered_files')

    # 5) start period task of removing stale files
    celery_app.conf.beat_schedule = {
        'remove_stale_pending_files': {
            'task': 'datams.celery.remove_stale_files_task',
            'schedule': app.config['DATA_FILES']['remove_stales_every'],
            # 'args': (PENDING_DIRECTORY,)
            'kwargs': dict(lock='remove_stale_files')
        },
    }

    # TODO: May want to follow similar pattern for loading pending and deleted files?
    return celery_app

# EXAMPLE OF HOW TO CHAIN TOGETHER MULTIPLE TASKS
# @shared_task(ignore_result=False)
# def task_1(arg):
#     result = step_1(arg)
#     return result
#
#
# @shared_task
# def task_2(result):
#     step_2(result)
#
#
# def chain_together_task1_and_task2(arg):
#     # chain the tasks together so result is piped to the next task
#     chain = task_1.s(arg) | task_2.s()
#     chain()