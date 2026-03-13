# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Waterpijl** is a water level monitoring and alerting system for Dutch water management. It fetches 5-day water level forecasts from the Dutch water authority (RWS - Rijkswaterstaat) API for the Nederhemert station and sends Dutch-language email alerts when levels are projected to exceed a configurable threshold.

## Commands

**Run locally:**
```bash
pip install -r requirements.txt
python src/main.py
```

**Build and run with Docker:**
```bash
docker build -t waterpijl:latest .
docker-compose up -d
```

There are no tests or linting configured.

## Architecture

Data flows through three modules:

1. **`src/waterlevel.py`** — Fetches forecast data from `https://rwsos.rws.nl/wb-api/dd/2.0/timeseries`, parses it into a pandas DataFrame (converting UTC timestamps to Europe/Amsterdam), detects the first threshold breach, generates a matplotlib plot (`waterlevel_plot.png`), and returns breach metadata.

2. **`src/main.py`** — Orchestrator: loads env vars (`THRESHOLD`, `EMAIL_USER`, `EMAIL_PASS`), calls `fetch_process_and_plot()`, and triggers email if a breach is detected.

3. **`src/email_setup.py`** — Sends a Dutch-language HTML email via Gmail SMTP with the plot attached. Recipients are `EMAIL_USER` and `jelle@teije.ma`.

### Docker scheduling

The container (Alpine Python 3.13) runs `src/main.py` via cron. The schedule is set at container startup by `entrypoint.sh` using the `CRON_SCHEDULE` env var (default: `0 8,20 * * *`).

## Configuration

Environment variables (via `.env` or Docker Compose):

| Variable | Description |
|---|---|
| `EMAIL_USER` | Gmail address used as sender and first recipient |
| `EMAIL_PASS` | Gmail app password |
| `ALERT_LEVEL` | Water level in cm +NAP above which an alert email is sent (e.g. `200`) |
| `LOCATION_CODE` | RWS station identifier (default: `matroos.AF_234.00` — Nederhemert) |
| `CRON_SCHEDULE` | Cron expression for when to run (default: `0 8,20 * * *`) |

## Dependencies

- `requests` — API calls to RWS
- `python-dotenv` — `.env` loading
- `pandas` — data parsing and processing
- `matplotlib` — plot generation
