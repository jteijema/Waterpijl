# Waterpijl

<img src="assets/icon.png" alt="Waterpijl icon" width="120" align="right">

Waterpijl monitors the 5-day water level forecast for **Nederhemert** from the Dutch water authority (RWS) and sends an email alert when levels are expected to exceed a configurable threshold.

Runs automatically at **08:00 and 20:00** daily via a Docker container with cron.

## Usage

Copy `.env.example` to `.env` and fill in your credentials:

```
EMAIL_USER=you@gmail.com
EMAIL_PASS=your-gmail-app-password
THRESHOLD=200
```

`THRESHOLD` is in cm +NAP.

Then run with Docker Compose:

```bash
docker-compose up -d
```

Or locally:

```bash
pip install -r requirements.txt
python main.py
```

## How it works

1. Fetches a 5-day water level forecast from the [RWS DD API](https://rwsos.rws.nl/wb-api/dd/2.0/timeseries) for station Nederhemert
2. Plots the forecast against the threshold and saves it as `waterlevel_plot.png`
3. If the threshold is breached, sends a Dutch-language email alert with the plot attached
