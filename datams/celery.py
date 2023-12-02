import functools
from typing import Tuple, Any
from flask import Flask
from celery import Celery, Task, shared_task

from datams.redis import get_value, set_value, acquire_lock, release_lock, is_locked
from datams.utils import remove_stale_files, update_and_append_to_checkins
from datams.db.queries.select import select_query

#  Note in order to know if value is ready application can check if the
#  `<key>_lock` key exists.  If it doesn't then it should be ready.  Otherwise
#  it is currently being computed and set


# NOTE: not the first argument of any methods decorated by this method should be `key`
#       this determines which lock to use
def requires_lock(_func=None, *, ignore_when_locked=False):
    def decorator_requires_lock(func):
        @functools.wraps(func)
        def wrapper_requires_lock(key, *args, **kwargs):
            # print(f"key: {key}")
            # print(f"args: {args}")
            # print(f"kwargs: {kwargs}")
            if not ignore_when_locked or not is_locked(key):
                acquire_lock(key)
                retval = func(key, *args, **kwargs)
                release_lock(key)
            return retval
        return wrapper_requires_lock
    if _func is None:
        return decorator_requires_lock
    else:
        return decorator_requires_lock(_func)


# define background tasks
@shared_task(name='compute_and_set')  # explicitly set task name because of wrapper
@requires_lock(ignore_when_locked=True)
def compute_and_set_task(key) -> None:
    # NOTE: Currently this method assumes all data coming from select_query is a pandas
    #        Dataframe.
    try:
        # if key is not implemented, release the lock and ignore the request
        value = select_query(data=key).to_json()
        set_value(key, value)
    except NotImplementedError:
        pass


@shared_task(name='update')
@requires_lock
def update_task(key, value: Any) -> None:
    # NOTE: if method isn't defined then value is simply set, but it is assumed that
    #       its type is compatible
    methods = dict(
        checkins=lambda x, y: str(update_and_append_to_checkins(get_value(x), y)),
    )
    method = methods.get(key, lambda x, y: y)
    set_value(key, method(key, value))


@shared_task(name='remove_stale_files')
@requires_lock
def remove_stale_files_task(key) -> None:
    remove_stale_files(get_value('checkins'))


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

    # 3) start background task of computing and setting various file types
    compute_and_set_task.delay('processed_files')
    compute_and_set_task.delay('pending_files')
    compute_and_set_task.delay('discovered_files')
    compute_and_set_task.delay('deleted_files')

    # 5) start period task of removing stale files
    celery_app.conf.beat_schedule = {
        'remove_stale_files': {
            'task': 'remove_stale_files',
            'schedule': app.config['DATA_FILES']['remove_stales_every'],
            'args': ('remove_stale_files',),
            # 'kwargs': dict(key='remove_stale_files')
        },
    }
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