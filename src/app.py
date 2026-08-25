import logging
import os
from datetime import UTC, datetime
from urllib.parse import unquote
from zoneinfo import ZoneInfo

if __name__ != "__main__":
    gunicorn_logger = logging.getLogger("gunicorn.error")
    root_logger = logging.getLogger()
    root_logger.handlers = gunicorn_logger.handlers
    root_logger.setLevel(gunicorn_logger.level)
else:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

logger = logging.getLogger(__name__)

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, send_file

from plot import render_forecast_plot, render_history_plot
from store import Store
from waterlevel import get_waterlevel_url

load_dotenv()

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.abspath(os.path.join(SRC_DIR, "..", "assets"))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(SRC_DIR, "..", "data"))
LOCATION_CODE = os.getenv("LOCATION_CODE", "matroos.AF_234.00")
ALERT_LEVEL = float(os.getenv("ALERT_LEVEL", 200))
CRON_SCHEDULE = os.getenv("CRON_SCHEDULE", "0 8,14,20 * * *")

DATABASE_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "waterpijl.db"))
os.makedirs(DATA_DIR, exist_ok=True)

app = Flask(__name__)

if __name__ != "__main__":
    app.logger.handlers = gunicorn_logger.handlers
    app.logger.setLevel(gunicorn_logger.level)

_store = Store(DATABASE_PATH)
_plot_cache = {"check_id": None, "bytes": None}
_history_cache = {"check_id": None, "bytes": None}


def format_dt(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(ZoneInfo("Europe/Amsterdam")).strftime("%Y-%m-%d %H:%M %Z")
    except Exception:
        logger.warning("Could not format datetime string: %s", iso_str)
        return iso_str


def format_dt_short(iso_str):
    try:
        dt = datetime.fromisoformat(iso_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(ZoneInfo("Europe/Amsterdam")).strftime("%d %b %H:%M")
    except Exception:
        return iso_str


def _peak_history(limit=14):
    return _store.check_history(limit=limit)


def _plot_bytes():
    check = _store.latest_with_samples()
    if check is None:
        return None
    if _plot_cache.get("check_id") != check["id"]:
        plot = render_forecast_plot(check["samples"], check["alert_level"], check["station"])
        _plot_cache.update(check_id=check["id"], bytes=plot)
    return _plot_cache["bytes"]


def _history_plot_bytes():
    checks = _peak_history()
    if not checks:
        return None
    latest_id = checks[0]["id"]
    if _history_cache.get("check_id") != latest_id:
        hist = render_history_plot(checks, checks[0]["alert_level"])
        _history_cache.update(check_id=latest_id, bytes=hist)
    return _history_cache["bytes"]


def _history_rows():
    rows = []
    for check in _store.check_history(limit=8):
        rows.append(
            {
                "started_at": format_dt_short(check["started_at"]),
                "status": check["status"],
                "peak": check["peak_value"],
                "error": check["error"],
            }
        )
    return rows


@app.route("/")
def index():
    check = _store.latest_check()
    return render_template(
        "dashboard.html",
        location_code=LOCATION_CODE,
        alert_level=os.getenv("ALERT_LEVEL", "200"),
        cron_schedule=CRON_SCHEDULE,
        last_run=format_dt(check["started_at"]) if check else None,
        last_run_short=format_dt_short(check["started_at"]) if check else None,
        breach_time=format_dt(check["breach_time"]) if check and check["breach_time"] else None,
        breach_value=check["breach_value"] if check else None,
        peak_value=check["peak_value"] if check else None,
        last_error=check["error"] if check else None,
        status=check["status"] if check else None,
        has_plot=_store.latest_with_samples() is not None,
        history=_history_rows(),
        has_history=bool(_store.check_history(limit=1)),
        api_url=unquote(get_waterlevel_url(datetime.now(UTC))),
    )


@app.route("/plot.png")
def plot():
    plot_bytes = _plot_bytes()
    if plot_bytes is None:
        return "No forecast data yet", 404
    from io import BytesIO

    return send_file(BytesIO(plot_bytes), mimetype="image/png")


@app.route("/plot/history.png")
def plot_history():
    plot_bytes = _history_plot_bytes()
    if plot_bytes is None:
        return "No history yet", 404
    from io import BytesIO

    return send_file(BytesIO(plot_bytes), mimetype="image/png")


@app.route("/api/status")
def api_status():
    check = _store.latest_check()
    if check is None:
        return jsonify({"status": "unknown", "has_data": False})
    return jsonify(
        {
            "status": check["status"],
            "started_at": check["started_at"],
            "alert_level": check["alert_level"],
            "station": check["station"],
            "breach_time": check["breach_time"],
            "breach_value": check["breach_value"],
            "error": check["error"],
        }
    )


@app.route("/api/forecast")
def api_forecast():
    check = _store.latest_with_samples()
    if check is None:
        return jsonify({"error": "No forecast data stored"}), 404
    return jsonify(
        {
            "check_id": check["id"],
            "station": check["station"],
            "alert_level": check["alert_level"],
            "status": check["status"],
            "checked_at": check["started_at"],
            "breach_time": check["breach_time"],
            "breach_value": check["breach_value"],
            "samples": check["samples"],
        }
    )


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


@app.route("/icon")
def icon():
    return send_file(os.path.join(ASSETS_DIR, "icon.png"), mimetype="image/png")


@app.route("/favicon.ico")
def favicon():
    return send_file(os.path.join(ASSETS_DIR, "favicon.ico"), mimetype="image/x-icon")


if __name__ == "__main__":
    host = os.getenv("WEBAPP_HOST", "0.0.0.0")
    port = int(os.getenv("WEBAPP_PORT", 7261))
    logger.info("Starting Flask app on %s:%s", host, port)
    app.run(host=host, port=port)
