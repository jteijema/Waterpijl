# Waterpijl

<img src="assets/icon.png" alt="Waterpijl icon" width="120" align="right">

Waterpijl monitors the 5-day water level forecast for any RWS station and sends an email alert when levels are expected to exceed a configurable alert level.

Runs automatically on a configurable cron schedule via Docker. A web dashboard is available to view the latest forecast and check status.

## Usage

Copy `.env.example` to `.env` and fill in your credentials:

```
EMAIL_USER=you@gmail.com
EMAIL_PASS=your-gmail-app-password
ALERT_LEVEL=200
LOCATION_CODE=matroos.AF_234.00
CRON_SCHEDULE=0 8,20 * * *
WEBAPP_HOST=0.0.0.0
WEBAPP_PORT=8080
```

Then run with Docker Compose:

```bash
docker-compose up -d
```

The dashboard will be available at `http://localhost:8080`.

Or run locally (no dashboard):

```bash
pip install -r requirements.txt
python src/main.py
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `EMAIL_USER` | — | Gmail address used as sender and first recipient |
| `EMAIL_PASS` | — | Gmail app password |
| `ALERT_LEVEL` | `200` | Water level in cm +NAP above which an alert email is sent |
| `LOCATION_CODE` | `matroos.AF_234.00` | RWS station identifier (default: Nederhemert) |
| `FORECAST_DAYS` | `5` | Days ahead to fetch from the RWS API (max 6 — the API will hang beyond that) |
| `CRON_SCHEDULE` | `0 8,20 * * *` | Cron expression for when to run checks |
| `WEBAPP_HOST` | `0.0.0.0` | Host for the web dashboard |
| `WEBAPP_PORT` | `8080` | Port for the web dashboard |

## How it works

1. Fetches a 5-day water level forecast from the [RWS DD API](https://rwsos.rws.nl/wb-api/dd/2.0/timeseries) for the configured station
2. Plots the forecast against the alert level and saves it as `waterlevel_plot.png`
3. If the alert level is exceeded, sends a Dutch-language email alert with the plot attached
4. The web dashboard shows the latest plot, last check result, and next scheduled run
