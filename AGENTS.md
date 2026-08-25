# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

**Waterpijl** is a water level monitoring and alerting system for Dutch water management. It fetches water level forecasts from the Dutch water authority (RWS - Rijkswaterstaat) API and sends Dutch-language email alerts when levels are projected to exceed a configurable alert level. A Flask dashboard shows the latest forecast and check status.

## Commands

Project managed with [uv](https://docs.astral.sh/uv/). Dependencies and dev tooling live in `pyproject.toml`, resolved by `uv.lock`.

**Run locally:**
```bash
uv sync
uv run python src/app.py
```

**Run tests and lint:**
```bash
uv run pytest
uv run ruff check src tests
```

**Build and run with Docker:**
```bash
docker compose up -d
```

The tests run in CI on every push/PR (`.github/workflows/ci.yml`), and Dependabot keeps `pyproject.toml`, the Docker base image, and Actions versions current (`.github/dependabot.yml`).

## Architecture

Two processes share a SQLite-free file-drop queue on the `/data` volume:

- **`src/app.py`** — Main app. Starts an APScheduler `BackgroundScheduler` with a `CronTrigger`, serves the Flask dashboard, and runs `run_check()` on schedule. Writes `status.json` to `DATA_DIR` after each check. On breach, instead of sending email, enqueues an alert job (JSON + plot copy) into the shared queue (`EMAIL_QUEUE_DIR`). Triggers an immediate check on startup if no plot exists yet.
- **`src/email_job.py`** — Producer. `enqueue_alert()` copies the plot and writes an `alert-<id>.json` job atomically into the shared queue dir.
- **`src/email_worker.py`** — Email sidecar container. Polls the same queue dir, renders the alert from the Jinja2 template, sends via Gmail SMTP, removes the job on success, and retries with exponential backoff (`.failed.json` after max attempts). Email credentials live only here.
- **`src/waterlevel.py`** — Fetches forecast data from the RWS DD API, parses it into a pandas DataFrame (UTC → Europe/Amsterdam), generates a matplotlib plot saved to `DATA_DIR`, and returns the first breach time and value (or `None, None`).
- **`email_template.txt`** — Jinja2 template for the alert email (subject + body). Path overridable via `EMAIL_TEMPLATE_FILE`.
- **`src/templates/dashboard.html`** — Jinja2 template for the Flask dashboard.
- **`assets/`** — Static files (icon, favicon). Referenced from `src/app.py` via absolute paths relative to `__file__`.
- **`tests/`** — pytest suite (breach detection, email render/retry, queue producer, status writing) run in CI.

Gunicorn serves the app with `--workers 1` to ensure only one scheduler instance runs. Plot, status, and queue data are persisted to a named Docker volume mounted at `/data` (configured via `DATA_DIR` env var).

## Configuration

| Variable | Default | Service | Description |
|---|---|---|---|
| `EMAIL_USER`| — | email | Gmail address used as the sender |
| `EMAIL_PASS` | — | email | Gmail app password |
| `EMAIL_TO` | `EMAIL_USER` | email | Recipient address for alert emails |
| `EMAIL_TEMPLATE_FILE` | `./email_template.txt` | email | Path to the Jinja2 alert email template |
| `EMAIL_QUEUE_DIR` | `$DATA_DIR/queue` | both | Shared outbox directory for alert jobs + plot copies |
| `EMAIL_POLL_INTERVAL` | `10` | email | Seconds between queue polls |
| `EMAIL_MAX_ATTEMPTS` | `10` | email | Max send attempts before a job is marked failed |
| `ALERT_LEVEL`| `200` | app | Water level in cm +NAP above which an alert is sent |
| `LOCATION_CODE` | `matroos.AF_234.00` | app | RWS station identifier (default: Nederhemert) |
| `FORECAST_DAYS` | `5` | app | Days ahead to fetch (max 6 — the RWS API hangs beyond that) |
| `CRON_SCHEDULE` | `0 8,20 * * *` | app | Cron expression for when to run checks |
| `WEBAPP_HOST` | `0.0.0.0` | app | Host to bind the web server to |
| `WEBAPP_PORT` | `7261` | app | Port for the web server |
| `DATA_DIR` | `./data` | both | Directory for plot, status, and queue persistence |
| `LOG_LEVEL` | `INFO` | both | Logging level |

## Dependencies

- `requests` — API calls to RWS
- `python-dotenv` — `.env` loading
- `pandas` — data parsing and processing
- `matplotlib` — plot generation
- `flask` — web dashboard
- `jinja2` — email and dashboard templates
- `gunicorn` — production WSGI server
- `apscheduler<4` — cron-based scheduling within the app process
- `pytest`, `ruff` — dev/test tooling (dev group in `pyproject.toml`)
