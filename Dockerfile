FROM python:3.7

RUN pip install pipenv==2018.10.9

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pipenv install --deploy --system

EXPOSE 5000

ENTRYPOINT ["python", "-u", "flat_application.py"]

COPY . /usr/src/app
