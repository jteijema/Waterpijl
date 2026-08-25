# AGENTS.md

This file provides guidance to AI coding agents when working with code in this repository.

## Project Overview

**Waterpijl** is a water level monitoring and alerting system for Dutch water management. It fetches water level forecasts from the Dutch water authority (RWS - Rijkswaterstaat) API and sends Dutch-language email alerts when levels are projected to exceed a configurable alert level. A Flask dashboard shows the latest forecast and check status.

## Commands

Project managed with [uv](https://docs.astral.sh/uv/). Dependencies and dev tooling live in `pyproject.toml`, resolved by `uv.lock`.

**Run locally:**
```bash
uv sync
uv run python src/app.py              # web dashboard
uv run python src/checker.py          # cron checker (separate terminal)
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

Three processes share the `/data` volume; SQLite (`${DB_PATH:-$DATA_DIR/waterpijl.db}`, WAL mode) is the source of truth, a file-drop queue handles alert handoff:

- **`src/app.py`** — Web process. Read-only Flask app: dashboard, `/api/status`, `/api/forecast`, `/plot.png` (rendered on request from stored samples, cached in memory). No scheduler, no API calls, no writes.
- **`src/checker.py`** — Checker container. Runs `run_check()` on an APScheduler cron, `fetch_forecast()` → `detect_breach()`, stores the check row + forecast samples in SQLite, and on breach calls `enqueue_alert()`. Runs an immediate first check if the DB is empty. Owns all writes to the DB.
- **`src/store.py`** — SQLite layer: `checks` (result per run) and `forecast_samples` (the series) tables. `latest_check()` / `latest_with_samples()` are the web's reads.
- **`src/waterlevel.py`** — RWS DD API client: `fetch_forecast()` returns `(DataFrame[timeStamp tz Europe/Amsterdam, value], station)`; `detect_breach(df, alert_level)` returns first breach `(time, value)` or `(None, None)`.
- **`src/plot.py`** — `render_forecast_plot(samples, alert_level, station)` → PNG bytes. Used by web (dashboard plot) and checker (email attachment).
- **`src/email_job.py`** — Producer. `enqueue_alert()` writes an `alert-<id>.json` job atomically into `EMAIL_QUEUE_DIR` (accepts either a `plot_path` or `plot_bytes` → copied to `<dir>/alert-<id>.png`).
- **`src/email_worker.py`** — Email sidecar container. Polls the queue dir, renders the alert from the Jinja2 template, sends via Gmail SMTP, removes the job on success, retries with exponential backoff (`.failed.json` after max attempts). Email credentials live only here.
- **`email_template.txt`** — Jinja2 template for the alert email (subject + body). Path overridable via `EMAIL_TEMPLATE_FILE`.
- **`src/templates/dashboard.html`** — Jinja2 template for the Flask dashboard.
- **`assets/`** — Static files (icon, favicon). Referenced from `src/app.py` via absolute paths relative to `__file__`.
- **`tests/`** — pytest suite (store CRUD, checker paths, web API/plot, email render/retry, queue producer, breach detection) run in CI.

Gunicorn serves the web app with `--workers 1` (no scheduler in this process anymore, but a single writer keeps everything simple). DB, queue, and plot caches live on the named Docker volume at `/data` (`DATA_DIR`).

### Data flow

```
RWS API ──► checker (cron) ──► SQLite (checks + samples)      web ──► /api/status, /api/forecast, /plot.png
                   │                │
                   └─ breach? ──► queue ──► email worker ──► Gmail
```

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
| `CRON_SCHEDULE` | `0 8,14,20 * * *` | app | Cron expression for when to run checks |
| `KEEP_DAYS` | `60` | app | How long check history is kept; older data is pruned each run |
| `DB_PATH` | `$DATA_DIR/waterpijl.db` | both | SQLite database file |
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
- `apscheduler<4` — cron-based scheduling within the checker process
- `pytest`, `ruff` — dev/test tooling (dev group in `pyproject.toml`)
