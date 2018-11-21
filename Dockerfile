FROM python:3.7-alpine as builder

RUN apk add --no-cache gcc python3-dev musl-dev alpine-sdk libffi-dev openssl-dev

RUN pip install pipenv==2018.10.9

COPY Pipfile Pipfile
COPY Pipfile.lock Pipfile.lock

RUN pipenv install --deploy --system

RUN pip uninstall --yes pipenv

RUN find /usr/local/lib/python3.7 -name '*.c' -delete
RUN find /usr/local/lib/python3.7 -name '*.pxd' -delete
RUN find /usr/local/lib/python3.7 -name '*.pyd' -delete
RUN find /usr/local/lib/python3.7 -name '__pycache__' | xargs rm -r
RUN rm -r /usr/local/lib/python3.7/config-3.7m-x86_64-linux-gnu/

FROM python:3.7-alpine

RUN apk add --no-cache openssl

COPY --from=builder /usr/local/lib/python3.7 /usr/local/lib/python3.7

COPY . /usr/src/app

WORKDIR /usr/src/app

EXPOSE 5000

CMD python -u flat_application.py
