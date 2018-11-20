FROM pypy:3-6

RUN pip install pipenv==2018.10.9

RUN mkdir -p /usr/src/app
WORKDIR /usr/src/app

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pipenv install --deploy --system

EXPOSE 5000

ENTRYPOINT ["pypy3", "-u", "flat_application.py"]

COPY . /usr/src/app
