FROM python:3.13-alpine

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

ENV UV_PYTHON_PREFERENCE=system
ENV PATH="/app/.venv/bin:$PATH"

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

COPY . .

ENV DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

RUN adduser -D -u 1001 appuser \
    && mkdir -p /data \
    && chown -R appuser:appuser /app /data

USER appuser

EXPOSE 7261

CMD gunicorn --bind ${WEBAPP_HOST:-0.0.0.0}:${WEBAPP_PORT:-7261} \
    --workers 1 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    --chdir /app/src app:app