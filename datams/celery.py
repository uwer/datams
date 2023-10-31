from flask import Flask
from celery import Celery, Task, shared_task
from datams.redis import set_files
from datams.db.queries.select import select_files


# define background tasks
@shared_task(ignore_result=False)
def get_files_task():
    df = select_files('file.root')
    return df.to_json()


@shared_task
def set_files_task(result):
    set_files(result)


def load_cache():
    # chain the tasks together so result is piped to the next task
    chain = get_files_task.s() | set_files_task.s()
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

    # 3) start background task of loading cache
    load_cache()

    return celery_app
