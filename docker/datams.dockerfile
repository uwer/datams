FROM ubuntu:22.04

WORKDIR /app


RUN apt update ; apt install software-properties-common -y
RUN apt install libpq-dev build-essential libgl1-mesa-glx git python3-pip python3-virtualenvwrapper -y
    
ENV WORKON_HOME=/app/run
ENV DATAMS_CONFIG="${WORKON_HOME}/config.yaml"
RUN git clone https://github.com/uwer/datams.git ; mkdir run ; cp datams/docker/config.yaml ./run/ ;\
	source /usr/share/virtualenvwrapper/virtualenvwrapper.sh;  mkvirtualenv datams ; \
   pip3 install -r datams/requirements.txt
   
RUN echo "" >> ~/.bashrc  ; echo "source /usr/share/virtualenvwrapper/virtualenvwrapper.sh" >> ~/.bashrc 

CMD ["gunicorn","--workers","3","--bind","unix:datams.sock","-m","007","wsgi:app"]