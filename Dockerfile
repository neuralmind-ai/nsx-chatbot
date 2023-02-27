FROM python:3.10.9

ENV TZ=America/Sao_Paulo

RUN apt-get update
RUN apt-get install cron -y

WORKDIR /whatsappbot

ADD ./requirements.txt ./
RUN pip install -r requirements.txt --ignore-installed ruamel-yaml
COPY ./src ./

RUN echo "*/10 * * * * root cd /whatsappbot && /usr/local/bin/python3 cronjobs/search_data_cleaner.py &>log.txt" >> /etc/crontab
CMD cron && uvicorn main:app --host 0.0.0.0 --port 80
