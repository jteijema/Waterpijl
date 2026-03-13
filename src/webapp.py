import os
import json
from datetime import datetime, timezone
from flask import Flask, send_file, render_template
from croniter import croniter

app = Flask(__name__)

PLOT_PATH = "/app/waterlevel_plot.png"
STATUS_FILE = "/app/status.json"

def load_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def next_run_time(cron_schedule):
    try:
        cron = croniter(cron_schedule, datetime.now(timezone.utc))
        return cron.get_next(datetime).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return "unknown"

def format_dt(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_str

@app.route("/")
def index():
    status = load_status()
    cron_schedule = os.getenv("CRON_SCHEDULE", "0 8,20 * * *")
    return render_template("dashboard.html",
        location_code=os.getenv("LOCATION_CODE", "matroos.AF_234.00"),
        alert_level=os.getenv("ALERT_LEVEL", "200"),
        last_run=format_dt(status["last_run"]) if status else None,
        breached=status.get("breached", False) if status else False,
        next_run=next_run_time(cron_schedule),
        cron_schedule=cron_schedule,
        has_plot=os.path.exists(PLOT_PATH),
    )

@app.route("/plot.png")
def plot():
    return send_file(PLOT_PATH, mimetype="image/png")

@app.route("/icon")
def icon():
    return send_file("/app/assets/icon.png", mimetype="image/png")

if __name__ == "__main__":
    host = os.getenv("WEBAPP_HOST", "0.0.0.0")
    port = int(os.getenv("WEBAPP_PORT", 8080))
    app.run(host=host, port=port)
