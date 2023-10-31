FROM ubuntu:22.04

WORKDIR /app


RUN apt update ; apt install software-properties-common -y
RUN apt install libpq-dev build-essential libgl1-mesa-glx git python3-pip python3-virtualenvwrapper -y
    
ENV DATAMS_CONFIG="/app/run/config.yml"
ENV DATAMS_ROOT=/app/datams
ENV SECRET_KEY="94c75b0757c0dc592d1cf5b877443d2ccc412561136abdd7246af32dad76365a"
ENV GOOGLE_KEY="773b951aa8457a0c6d0de74fa4687701e5b603c4829c6bce244e171884a640e3"

RUN git clone https://github.com/uwer/datams.git ;\
    mkdir -p run/uploads/{submitted,pending} ;\
    cp datams/docker/config.yml ./run/ ;\
    pip3 install -r datams/requirements.txt; \
    cp datams/docker/run_*.sh /app/ ;\
    chmod 750 /app/run_*.sh

CMD ["run_gu.sh"]