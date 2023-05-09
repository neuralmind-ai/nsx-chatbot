FROM python:3.10.9

ENV TZ=America/Sao_Paulo

RUN apt-get update

WORKDIR /whatsappbot

ADD ./requirements.txt ./
RUN pip install -r requirements.txt --ignore-installed ruamel-yaml
COPY ./src ./

CMD uvicorn main:app --host 0.0.0.0 --port 9000
