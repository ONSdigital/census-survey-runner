FROM python:3.7

RUN pip install pipenv==2018.10.9
RUN apt update && apt install -y libsnappy-dev

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

ENV AWS_DEFAULT_REGION eu-west-1
ENV GUNICORN_WORKERS 3
ENV GUNICORN_WORKER_CLASS gevent

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pipenv install --deploy --system

EXPOSE 5000

ENTRYPOINT ["sh", "docker-entrypoint.sh"]

COPY . /usr/src/app
