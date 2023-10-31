#!/bin/bash


cd ${DATAMS_ROOT}
gunicorn --workers=3 'datams:create_app()'