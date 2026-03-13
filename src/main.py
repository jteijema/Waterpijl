import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from waterlevel import fetch_process_and_plot
from email_setup import send_alert

load_dotenv()
ALERT_LEVEL = float(os.getenv("ALERT_LEVEL", 200))
STATUS_FILE = "/app/status.json"

def write_status(breached: bool, breach_time=None, breach_value=None):
    status = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "breached": breached,
        "breach_time": breach_time.isoformat() if breach_time else None,
        "breach_value": breach_value,
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

def main():
    print("Running water level check and generating plot...")
    try:
        breach_time, breach_value, plot_path = fetch_process_and_plot(ALERT_LEVEL)

        if plot_path:
            print(f"Plot saved successfully to {plot_path}")

        if breach_time is not None:
            print(f"Alert level exceeded! First occurrence at {breach_time} with {breach_value} cm.")
            write_status(True, breach_time, breach_value)
            send_alert(breach_time, breach_value, plot_path)
        else:
            print("Levels remain below alert level. No email sent.")
            write_status(False)

    except Exception as e:
        print(f"Error during execution: {e}")

if __name__ == "__main__":
    main()
