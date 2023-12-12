FROM nginx:mainline-alpine3.18-slim

RUN mkdir /etc/nginx/modules-enabled ; 
COPY ./installation/datams /etc/nginx/sites-enabled/datams
COPY ./installation/nginx.conf /etc/nginx/nginx.conf




