import pandas as pd
import requests
import matplotlib.pyplot as plt
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
import os

LOCATION_CODE = os.getenv("LOCATION_CODE", "matroos.AF_234.00")

def get_waterlevel_url(start_date: datetime) -> str:
    end_date = start_date + timedelta(days=5)
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
        request = requests.get(url)
        return request.json()
    except Exception as e:
        print(f"API Fetch Error: {e}")
        return {}

def fetch_process_and_plot(alert_level: float):
    now = datetime.now(timezone.utc)
    url = get_waterlevel_url(now)
    data = get_data_from_url(url)

    if not data or 'results' not in data or not data['results']:
        raise ValueError("No valid data returned from API")

    events = data['results'][0].get('events', [])
    if not events:
        raise ValueError("No events found in the API response")

    # Build DataFrame and format types
    df = pd.DataFrame(events)
    df['value'] = pd.to_numeric(df['value']).round(2)
    df['timeStamp'] = pd.to_datetime(df['timeStamp']).dt.tz_convert('Europe/Amsterdam')

    # Generate and save plot
    plot_path = "waterlevel_plot.png"
    plt.figure(figsize=(10, 6))
    plt.plot(df['timeStamp'], df['value'], label='Water Level (cm)', color='blue')

    # Add horizontal alert level line
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

    # Determine first occurrence above alert level
    breaches = df[df['value'] > alert_level]
    if not breaches.empty:
        first_breach = breaches.iloc[0]
        return first_breach['timeStamp'], first_breach['value'], plot_path
        
    return None, None, plot_path