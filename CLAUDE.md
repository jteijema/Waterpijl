# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Waterpijl** is a water level monitoring and alerting system for Dutch water management. It fetches 5-day water level forecasts from the Dutch water authority (RWS - Rijkswaterstaat) API for the Nederhemert station and sends Dutch-language email alerts when levels are projected to exceed a configurable threshold.

## Commands

**Run locally:**
```bash
pip install -r requirements.txt
python main.py
```

**Build and run with Docker:**
```bash
docker build -t waterpijl:latest .
docker-compose up -d
```

There are no tests or linting configured.

## Architecture

Data flows through three modules:

1. **`waterlevel.py`** — Fetches forecast data from `https://rwsos.rws.nl/wb-api/dd/2.0/timeseries`, parses it into a pandas DataFrame (converting UTC timestamps to Europe/Amsterdam), detects the first threshold breach, generates a matplotlib plot (`waterlevel_plot.png`), and returns breach metadata.

2. **`main.py`** — Orchestrator: loads env vars (`THRESHOLD`, `EMAIL_USER`, `EMAIL_PASS`), calls `fetch_process_and_plot()`, and triggers email if a breach is detected.

3. **`email_setup.py`** — Sends a Dutch-language HTML email via Gmail SMTP with the plot attached. Recipients are `EMAIL_USER` and `jelle@teije.ma`.

### Docker scheduling

The container (Alpine Python 3.13) runs `main.py` via cron at **08:00 and 20:00 daily**. `entrypoint.sh` starts the cron daemon on container startup.

## Configuration

Environment variables (via `.env` or Docker Compose):

| Variable | Description |
|---|---|
| `EMAIL_USER` | Gmail address used as sender and first recipient |
| `EMAIL_PASS` | Gmail app password |
| `THRESHOLD` | Water level threshold in cm +NAP (e.g. `200`) |

## Dependencies

- `requests` — API calls to RWS
- `python-dotenv` — `.env` loading
- `pandas` — data parsing and processing
- `matplotlib` — plot generation
