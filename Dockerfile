FROM python:3.13-alpine

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

EXPOSE 7261

CMD gunicorn --bind ${WEBAPP_HOST:-0.0.0.0}:${WEBAPP_PORT:-7261} \
    --workers 1 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --chdir /app/src app:app