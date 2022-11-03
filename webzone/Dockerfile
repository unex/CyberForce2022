FROM python:3.10

RUN apt-get update && apt-get install -y libldap2-dev libsasl2-dev libssl-dev

COPY . /app
WORKDIR /app

EXPOSE 8000

RUN pip install pipenv
RUN pipenv install --system --deploy

CMD ["pipenv", "run", "prod"]
