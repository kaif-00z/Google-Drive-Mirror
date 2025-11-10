FROM python:3.14.0-slim-buster

RUN mkdir /app && chmod 777 /app
WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive
COPY . .

RUN apt-get -qq update && apt-get upgrade -y
RUN pip3 install --no-cache-dir --upgrade -r requirements.txt

CMD ["bash", "run.sh"]