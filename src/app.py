import os
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from flask import Flask, send_file, render_template
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from waterlevel import fetch_process_and_plot
from email_setup import send_alert

load_dotenv()

SRC_DIR     = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR  = os.path.join(SRC_DIR, '..', 'assets')
DATA_DIR    = os.getenv("DATA_DIR", os.path.join(SRC_DIR, '..', 'data'))
ALERT_LEVEL = float(os.getenv("ALERT_LEVEL", 200))
CRON_SCHEDULE = os.getenv("CRON_SCHEDULE", "0 8,20 * * *")
PLOT_PATH   = os.path.join(DATA_DIR, "waterlevel_plot.png")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")

os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

def write_status(breached: bool, breach_time=None, breach_value=None):
    status = {
        "last_run": datetime.now(timezone.utc).isoformat(),
        "breached": breached,
        "breach_time": breach_time.isoformat() if breach_time else None,
        "breach_value": breach_value,
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f)

def run_check():
    print("Running water level check...")
    try:
        breach_time, breach_value = fetch_process_and_plot(ALERT_LEVEL, PLOT_PATH)
        if breach_time is not None:
            print(f"Alert level exceeded at {breach_time} with {breach_value} cm.")
            write_status(True, breach_time, breach_value)
            send_alert(breach_time, breach_value, PLOT_PATH)
        else:
            print("Levels remain below alert level. No email sent.")
            write_status(False)
    except Exception as e:
        print(f"Error during check: {e}")

def load_status():
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

def format_dt(iso_str):
    try:
        return datetime.fromisoformat(iso_str).strftime("%Y-%m-%d %H:%M UTC")
    except Exception:
        return iso_str

scheduler = BackgroundScheduler()
job = scheduler.add_job(run_check, CronTrigger.from_crontab(CRON_SCHEDULE))
scheduler.start()

if not os.path.exists(PLOT_PATH):
    print("No plot found, running initial check...")
    scheduler.add_job(run_check)

@app.route("/")
def index():
    status = load_status()
    next_run = job.next_run_time.strftime("%Y-%m-%d %H:%M UTC") if job.next_run_time else "unknown"
    return render_template("dashboard.html",
        location_code=os.getenv("LOCATION_CODE", "matroos.AF_234.00"),
        alert_level=os.getenv("ALERT_LEVEL", "200"),
        last_run=format_dt(status["last_run"]) if status else None,
        breached=status.get("breached", False) if status else False,
        next_run=next_run,
        cron_schedule=CRON_SCHEDULE,
        has_plot=os.path.exists(PLOT_PATH),
    )

@app.route("/plot.png")
def plot():
    return send_file(PLOT_PATH, mimetype="image/png")

@app.route("/icon")
def icon():
    return send_file(os.path.join(ASSETS_DIR, 'icon.png'), mimetype="image/png")

@app.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(ASSETS_DIR, 'favicon.ico'), mimetype="image/x-icon")

if __name__ == "__main__":
    host = os.getenv("WEBAPP_HOST", "0.0.0.0")
    port = int(os.getenv("WEBAPP_PORT", 7261))
    app.run(host=host, port=port)
