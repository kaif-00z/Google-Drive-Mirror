FROM python:3.14.0-alpine

RUN mkdir /app && chmod 777 /app
WORKDIR /app

COPY . .

RUN apk update
RUN pip3 install --no-cache-dir -r requirements.txt

CMD ["sh", "run.sh"]