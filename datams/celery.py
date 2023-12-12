from typing import Any
from flask import Flask
from celery import Celery, Task, shared_task

from datams.redis import (get_value, set_value, set_working, set_finished,
                          remove_stale_vkeys, is_working, requires_lock, get_redis)
from datams.utils import (remove_stale_files, update_and_append_to_checkins,
                          get_valid_checkins)
from datams.db.queries.select import select_query

#  Note in order to know if value is ready application can check if the
#  `<key>_lock` key exists.  If it doesn't then it should be ready.  Otherwise
#  it is currently being computed and set


# define background tasks
@shared_task(name='compute_and_set')
def compute_and_set_task(key) -> None:
    # NOTE: Currently this method assumes all data coming from select_query is a pandas
    #        Dataframe.
    set_working(key)
    value = select_query(data=key).to_json()
    set_value(key, value)
    set_finished(key)


@shared_task(name='set_vkey')
def set_vkey_task(_, vkey):
    set_working(vkey)
    root_key = '.'.join(vkey.split('.')[3:])
    value = get_value(root_key).to_json()
    set_value(vkey, value)
    set_finished(vkey)


def update_vkey(vkey):
    set_working(vkey)
    root_key = '.'.join(vkey.split('.')[3:])
    chain = (compute_and_set_task.s(root_key) | set_vkey_task.s(vkey))
    chain()


@shared_task(name='update')
@requires_lock
def update_task(key, value: Any) -> None:
    # NOTE: if method isn't defined then value is simply set, but it is assumed that
    #       its type is compatible
    redis = get_redis()
    methods = dict(
        checkins=lambda x, y: str(update_and_append_to_checkins(get_value(x), y)),
    )
    new_value = methods.get(key, lambda x, y: y)(key, value)
    # can't use the redis.set_value or we'll end up in deadlock
    redis.set(key, new_value)


@shared_task(name='remove_stales')
def remove_stales_task() -> None:
    valid_uids = [uid for uid, _ in get_valid_checkins(get_value('checkins'))]
    remove_stale_files(valid_uids)
    remove_stale_vkeys(valid_uids)


def task_complete(key) -> bool:
    return False if is_working(key) else True


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
            # 'args': ('remove_stales',),
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