import logging
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import matplotlib.pyplot as plt
import pandas as pd
import requests

logger = logging.getLogger(__name__)

LOCATION_CODE = os.getenv("LOCATION_CODE", "matroos.AF_234.00")
# Max 6 days — the RWS API will hang on requests beyond that
try:
    FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", 5))
except ValueError:
    logger.warning("Invalid FORECAST_DAYS value, falling back to 5.")
    FORECAST_DAYS = 5

if FORECAST_DAYS > 6:
    logger.warning("FORECAST_DAYS=%s exceeds maximum of 6. Clamping to 6.", FORECAST_DAYS)
    FORECAST_DAYS = 6

if FORECAST_DAYS < 1:
    logger.warning("FORECAST_DAYS=%s is invalid. Falling back to 1.", FORECAST_DAYS)
    FORECAST_DAYS = 1

logger.info("Water level module configured with LOCATION_CODE=%s, FORECAST_DAYS=%s", LOCATION_CODE, FORECAST_DAYS)

def get_waterlevel_url(start_date: datetime) -> str:
    end_date = start_date + timedelta(days=FORECAST_DAYS)
    start_str = quote(start_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end_str = quote(end_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

    url = (
        f"https://rwsos.rws.nl/wb-api/dd/2.0/timeseries"
        f"?observationTypeId=waterlevel"
        f"&sourceName=fews_rmm_km"
        f"&&locationCode={LOCATION_CODE}"
        f"&&startTime={start_str}"
        f"&endTime={end_str}"
    )
    logger.info("Built water level API URL for start=%s end=%s", start_date.isoformat(), end_date.isoformat())
    logger.debug("Water level API URL: %s", url)
    return url

def get_data_from_url(url: str) -> dict:
    logger.info("Fetching water level data from API")
    try:
        response = requests.get(url, timeout=(10, 30))
        response.raise_for_status()
        payload = response.json()
        logger.info("Received API response with status=%s", response.status_code)
        return payload
    except requests.exceptions.Timeout:
        logger.error("API fetch timed out (connect=10s, read=30s).")
        return {}
    except requests.exceptions.RequestException as e:
        logger.error("API fetch request failed: %s", e)
        return {}
    except ValueError as e:
        logger.error("API fetch invalid JSON response: %s", e)
        return {}

def fetch_process_and_plot(alert_level: float, plot_path: str):
    now = datetime.now(timezone.utc)
    logger.info("Starting forecast fetch/process cycle at %s with alert_level=%s", now.isoformat(), alert_level)

    url = get_waterlevel_url(now)
    data = get_data_from_url(url)

    if not data or 'results' not in data or not data['results']:
        logger.error("No valid data returned from API")
        raise ValueError("No valid data returned from API")

    events = data['results'][0].get('events', [])
    if not events:
        logger.error("No events found in the API response")
        raise ValueError("No events found in the API response")

    logger.info("Processing %s forecast events", len(events))
    df = pd.DataFrame(events)
    df['value'] = pd.to_numeric(df['value']).round(2)
    df['timeStamp'] = pd.to_datetime(df['timeStamp']).dt.tz_convert('Europe/Amsterdam')

    logger.debug("Preparing plot at %s", plot_path)
    plt.figure(figsize=(10, 6))
    plt.plot(df['timeStamp'], df['value'], label='Water Level (cm)', color='blue')
    plt.axhline(y=alert_level, color='red', linestyle='--', label=f'Alert level ({alert_level} cm)')

    station_name = data['results'][0]['location']['properties']['locationName']
    plt.title(f'Water Level Forecast: {station_name}')
    plt.xlabel('Date')
    plt.ylabel('Water Level (cm +NAP)')
    plt.legend()
    plt.grid(True)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(plot_path)
    plt.close()
    logger.info("Saved forecast plot to %s for station=%s", plot_path, station_name)

    breaches = df[df['value'] > alert_level]
    if not breaches.empty:
        first_breach = breaches.iloc[0]
        logger.warning(
            "Alert threshold breached at %s with value=%s (alert_level=%s)",
            first_breach['timeStamp'],
            first_breach['value'],
            alert_level,
        )
        return first_breach['timeStamp'], first_breach['value']

    logger.info("No alert threshold breach found in forecast")
    return None, None
