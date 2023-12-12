#!/bin/bash


cd ${DATAMS_ROOT}
celery --app make_celery worker --loglevel=DEBUG --pool=solo