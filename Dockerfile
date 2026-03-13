FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/data

EXPOSE 8080

CMD gunicorn --bind ${WEBAPP_HOST:-0.0.0.0}:${WEBAPP_PORT:-8080} --workers 1 --chdir /app/src app:app
