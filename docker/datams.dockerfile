FROM ubuntu:22.04

WORKDIR /app


RUN apt update ; apt install software-properties-common -y
RUN apt install libpq-dev build-essential libgl1-mesa-glx git python3-pip python3-virtualenvwrapper -y
    
ENV DATAMS_CONFIG="/app/run/config.yml"
ENV DATAMS_ROOT=/app/datams
RUN git clone https://github.com/uwer/datams.git ; mkdir run ; cp datams/docker/config.yml ./run/ ;  pip3 install -r datams/requirements.txt; \
    cp datams/docker/run_gu.sh /app/run.sh ; chmod 750 /app/run.sh

CMD ["run.sh"]