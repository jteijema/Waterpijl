import logging
import os
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pandas as pd
import requests

logger = logging.getLogger(__name__)

FETCH_RETRIES = int(os.getenv("FETCH_RETRIES", 3))
FETCH_RETRY_DELAY = float(os.getenv("FETCH_RETRY_DELAY", 5))

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


def validate_config():
    """Fail fast if configuration would produce a useless API query."""
    if not LOCATION_CODE or not LOCATION_CODE.strip():
        raise SystemExit(
            "LOCATION_CODE is not set. Set it to an RWS station identifier "
            "(e.g. matroos.AF_234.00) via the LOCATION_CODE env var."
        )


def get_waterlevel_url(start_date: datetime) -> str:
    if not LOCATION_CODE or not LOCATION_CODE.strip():
        raise ValueError("LOCATION_CODE is not set; cannot build a water level API URL")
    end_date = start_date + timedelta(days=FORECAST_DAYS)
    start_str = quote(start_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end_str = quote(end_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

    url = (
        f"https://rwsos.rws.nl/wb-api/dd/2.0/timeseries"
        f"?observationTypeId=waterlevel"
        f"&sourceName=fews_rmm_km"
        f"&locationCode={LOCATION_CODE}"
        f"&startTime={start_str}"
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


def describe_empty_response(payload):
    """Return a terse reason for why payload has no usable forecast."""
    if not payload:
        return "empty body"
    if "results" not in payload:
        return f"no 'results' key; keys={list(payload.keys())}"
    if not payload["results"]:
        return "'results' is empty list"
    try:
        inner = payload["results"][0]
        if not inner.get("events"):
            inner_keys = list(inner.keys())
            event_full = inner.get("events")
            return f"results[0] has no events; keys={inner_keys}; events={event_full!r}"
    except (IndexError, TypeError) as e:
        return f"unexpected results shape: {e}"
    return "unknown"


def parse_forecast(payload: dict) -> pd.DataFrame:
    if not payload or "results" not in payload or not payload["results"]:
        raise ValueError("No valid data returned from API")

    events = payload["results"][0].get("events", [])
    if not events:
        raise ValueError("No events found in the API response")

    df = pd.DataFrame(events)
    df["value"] = pd.to_numeric(df["value"]).round(2)
    df["timeStamp"] = pd.to_datetime(df["timeStamp"]).dt.tz_convert("Europe/Amsterdam")
    return df[["timeStamp", "value"]]


def station_name(payload: dict) -> str:
    try:
        return payload["results"][0]["location"]["properties"]["locationName"]
    except (KeyError, IndexError, TypeError):
        logger.warning("Could not read station name from API response")
        return "unknown"


def has_forecast_data(payload):
    """True only if the payload contains at least one forecast event."""
    return bool(payload and payload.get("results")
                and payload["results"][0].get("events"))


def fetch_forecast():
    now = datetime.now(UTC)
    logger.info("Starting forecast fetch at %s", now.isoformat())
    url = get_waterlevel_url(now)

    payload = None
    for attempt in range(1, FETCH_RETRIES + 1):
        payload = get_data_from_url(url)
        if has_forecast_data(payload):
            break
        logger.warning(
            "API returned no usable data (attempt %d/%d): %s",
            attempt, FETCH_RETRIES, describe_empty_response(payload),
        )
        if attempt < FETCH_RETRIES:
            time.sleep(FETCH_RETRY_DELAY)
    else:
        raise ValueError(f"Failed to fetch forecast from the RWS API after {FETCH_RETRIES} attempts")

    df = parse_forecast(payload)
    logger.info("Parsed %s forecast events for station=%s", len(df), station_name(payload))
    return df, station_name(payload)


def detect_breach(df: pd.DataFrame, alert_level: float):
    breaches = df[df["value"] > alert_level]
    if not breaches.empty:
        first = breaches.iloc[0]
        logger.warning(
            "Alert threshold breached at %s with value=%s (alert_level=%s)",
            first["timeStamp"], first["value"], alert_level,
        )
        return first["timeStamp"], first["value"]
    logger.info("No alert threshold breach found in forecast")
    return None, None
