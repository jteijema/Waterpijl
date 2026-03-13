# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Waterpijl** is a water level monitoring and alerting system for Dutch water management. It fetches water level forecasts from the Dutch water authority (RWS - Rijkswaterstaat) API and sends Dutch-language email alerts when levels are projected to exceed a configurable alert level. A Flask dashboard shows the latest forecast and check status.

## Commands

**Run locally:**
```bash
pip install -r requirements.txt
python app.py
```

**Build and run with Docker:**
```bash
docker-compose up -d
```

There are no tests or linting configured.

## Architecture

A single process runs the Flask web app and the scheduler together:

- **`app.py`** — Entry point. Starts an APScheduler `BackgroundScheduler` with a `CronTrigger`, serves the Flask dashboard, and runs `run_check()` on schedule. Writes `status.json` to `DATA_DIR` after each check.
- **`waterlevel.py`** — Fetches forecast data from the RWS DD API, parses it into a pandas DataFrame (UTC → Europe/Amsterdam), generates a matplotlib plot saved to `DATA_DIR`, and returns the first breach time and value (or `None, None`).
- **`email_setup.py`** — Sends a Dutch-language email via Gmail SMTP with the plot attached.
- **`templates/dashboard.html`** — Jinja2 template for the Flask dashboard.

Gunicorn serves the app with `--workers 1` to ensure only one scheduler instance runs. Plot and status data are persisted to a named Docker volume mounted at `/data` (env: `DATA_DIR`).

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EMAIL_USER` | — | Gmail address used as the sender |
| `EMAIL_PASS` | — | Gmail app password |
| `EMAIL_TO` | `EMAIL_USER` | Recipient address for alert emails |
| `ALERT_LEVEL` | `200` | Water level in cm +NAP above which an alert is sent |
| `LOCATION_CODE` | `matroos.AF_234.00` | RWS station identifier (default: Nederhemert) |
| `FORECAST_DAYS` | `5` | Days ahead to fetch (max 6 — the RWS API hangs beyond that) |
| `CRON_SCHEDULE` | `0 8,20 * * *` | Cron expression for when to run checks |
| `WEBAPP_HOST` | `0.0.0.0` | Host to bind the web server to |
| `WEBAPP_PORT` | `8080` | Port for the web server |
| `DATA_DIR` | `./data` | Directory for plot and status file persistence |

## Dependencies

- `requests` — API calls to RWS
- `python-dotenv` — `.env` loading
- `pandas` — data parsing and processing
- `matplotlib` — plot generation
- `flask` — web dashboard
- `gunicorn` — production WSGI server
- `apscheduler<4` — cron-based scheduling within the app process
