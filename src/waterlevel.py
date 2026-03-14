import pandas as pd
import requests
import matplotlib.pyplot as plt
import os
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

LOCATION_CODE = os.getenv("LOCATION_CODE", "matroos.AF_234.00")
# Max 6 days — the RWS API will hang on requests beyond that
try:
    FORECAST_DAYS = int(os.getenv("FORECAST_DAYS", 5))
except ValueError:
    print("Invalid FORECAST_DAYS value, falling back to 5.")
    FORECAST_DAYS = 5

if FORECAST_DAYS > 6:
    print(f"FORECAST_DAYS={FORECAST_DAYS} exceeds maximum of 6. Clamping to 6.")
    FORECAST_DAYS = 6

if FORECAST_DAYS < 1:
    print(f"FORECAST_DAYS={FORECAST_DAYS} is invalid. Falling back to 1.")
    FORECAST_DAYS = 1

def get_waterlevel_url(start_date: datetime) -> str:
    end_date = start_date + timedelta(days=FORECAST_DAYS)
    start_str = quote(start_date.strftime("%Y-%m-%dT%H:%M:%SZ"))
    end_str = quote(end_date.strftime("%Y-%m-%dT%H:%M:%SZ"))

    return (
        f"https://rwsos.rws.nl/wb-api/dd/2.0/timeseries"
        f"?observationTypeId=waterlevel"
        f"&sourceName=fews_rmm_km"
        f"&&locationCode={LOCATION_CODE}"
        f"&&startTime={start_str}"
        f"&endTime={end_str}"
    )

def get_data_from_url(url: str) -> dict:
    try:
        response = requests.get(url, timeout=(10, 30))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        print("API Fetch Error: request timed out (connect=10s, read=30s).")
        return {}
    except requests.exceptions.RequestException as e:
        print(f"API Fetch Error: {e}")
        return {}
    except ValueError as e:
        print(f"API Fetch Error: invalid JSON response: {e}")
        return {}

def fetch_process_and_plot(alert_level: float, plot_path: str):
    now = datetime.now(timezone.utc)
    data = get_data_from_url(get_waterlevel_url(now))

    if not data or 'results' not in data or not data['results']:
        raise ValueError("No valid data returned from API")

    events = data['results'][0].get('events', [])
    if not events:
        raise ValueError("No events found in the API response")

    df = pd.DataFrame(events)
    df['value'] = pd.to_numeric(df['value']).round(2)
    df['timeStamp'] = pd.to_datetime(df['timeStamp']).dt.tz_convert('Europe/Amsterdam')

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

    breaches = df[df['value'] > alert_level]
    if not breaches.empty:
        first_breach = breaches.iloc[0]
        return first_breach['timeStamp'], first_breach['value']

    return None, None
