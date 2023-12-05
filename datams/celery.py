import functools
from typing import Tuple, Any

import pandas as pd
from flask import Flask
from celery import Celery, Task, shared_task

from datams.redis import (get_value, set_value, acquire_lock, release_lock, is_locked,
                          remove_stale_vkeys)
from datams.utils import (remove_stale_files, update_and_append_to_checkins,
                          get_valid_checkins)
from datams.db.queries.select import select_query

#  Note in order to know if value is ready application can check if the
#  `<key>_lock` key exists.  If it doesn't then it should be ready.  Otherwise
#  it is currently being computed and set


# NOTE: not the first argument of any methods decorated by this method should be `key`
#       this determines which lock to use
# TODO: Add ability to have multiple locks, but beware of dead-locking
def requires_lock(_func=None, *, ignore_when_locked=False):
    def decorator_requires_lock(func):
        @functools.wraps(func)
        def wrapper_requires_lock(key, *args, **kwargs):
            # print(f"key: {key}")
            # print(f"args: {args}")
            # print(f"kwargs: {kwargs}")
            was_locked = is_locked(key)
            acquire_lock(key)
            retval = None
            if not (was_locked and ignore_when_locked):
                retval = func(key, *args, **kwargs)
            release_lock(key)
            return retval
        return wrapper_requires_lock
    if _func is None:
        return decorator_requires_lock
    else:
        return decorator_requires_lock(_func)


# define background tasks
@shared_task(name='compute_and_set')
@requires_lock(ignore_when_locked=True)  # this still waits to get acquire the lock
def compute_and_set_task(key) -> None:
    # NOTE: Currently this method assumes all data coming from select_query is a pandas
    #        Dataframe.
    value = select_query(data=key).to_json()
    set_value(key, value)


@shared_task(name='set_vkey')
def set_vkey_task(_, key):
    root_key = '_'.join(key.split('_')[2:])
    value = get_value(root_key).to_json()
    set_value(key, value)


@requires_lock
def update_vkey(vkey):
    root_key = '_'.join(vkey.split('_')[2:])
    chain = (compute_and_set_task.s(root_key) | set_vkey_task.s(vkey))
    chain()


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


@shared_task(name='remove_stales')
@requires_lock
def remove_stales_task(key) -> None:
    valid_uids = [uid for uid, _ in get_valid_checkins(get_value('checkins'))]
    remove_stale_files(valid_uids)
    remove_stale_vkeys(valid_uids)



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
            'task': 'remove_stales',
            'schedule': app.config['DATA_FILES']['remove_stales_every'],
            'args': ('remove_stales',),
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