FROM ubuntu:22.04

WORKDIR /app


RUN apt update ; apt install software-properties-common -y
RUN apt install libpq-dev build-essential libgl1-mesa-glx git python3-pip python3-virtualenvwrapper -y
    
ENV DATAMS_CONFIG="/app/run/config.yml"
ENV DATAMS_ROOT=/app/datams
RUN git clone https://github.com/uwer/datams.git ; mkdir run ; cp datams/docker/config.yml ./run/ ;  pip3 install -r datams/requirements.txt; \
    cp datams/docker/run_*.sh /app/ ; chmod 750 /app/run_*.sh

CMD ["run_gu.sh"]