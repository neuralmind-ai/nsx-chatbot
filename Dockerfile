FROM tiangolo/uvicorn-gunicorn-fastapi:python3.8

ENV TZ=America/Sao_Paulo

ADD ./requirements.txt /app
RUN pip install -r requirements.txt --ignore-installed ruamel-yaml
COPY ./src /app
