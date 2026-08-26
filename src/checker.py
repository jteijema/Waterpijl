import logging
import os
import time

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv

from email_job import enqueue_alert
from plot import render_forecast_plot
from store import Store
from waterlevel import detect_breach, fetch_forecast, validate_config

logger = logging.getLogger(__name__)

load_dotenv()

DATA_DIR = os.getenv("DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
ALERT_LEVEL = float(os.getenv("ALERT_LEVEL", 200))
CRON_SCHEDULE = os.getenv("CRON_SCHEDULE", "0 8,14,20 * * *")
KEEP_DAYS = int(os.getenv("KEEP_DAYS", 60))

os.makedirs(DATA_DIR, exist_ok=True)
store = Store()


def run_check():
    logger.info("Running water level check (alert_level=%s)", ALERT_LEVEL)
    try:
        df, station = fetch_forecast()
        breach_time, breach_value = detect_breach(df, ALERT_LEVEL)
        peak_value = float(df["value"].max())
        samples = [
            {"time": ts.isoformat(), "value": float(value)}
            for ts, value in zip(df["timeStamp"], df["value"])
        ]
        check_id = store.add_check(
            status="breach" if breach_time else "ok",
            alert_level=ALERT_LEVEL,
            station=station,
            breach_time=breach_time,
            breach_value=breach_value,
            peak_value=peak_value,
            samples=samples,
        )

        if breach_time:
            logger.warning("Alert level exceeded at %s with %s cm", breach_time, breach_value)
            plot_bytes = render_forecast_plot(samples, ALERT_LEVEL, station)
            enqueue_alert(breach_time, breach_value, plot_bytes=plot_bytes)
        else:
            logger.info("Levels remain below alert level. No email enqueued.")
        logger.info("Stored check id=%s status=%s", check_id, "breach" if breach_time else "ok")
    except Exception as e:
        logger.exception("Error during check: %s", e)
        store.add_check(status="error", alert_level=ALERT_LEVEL, error=str(e))
    try:
        removed = store.prune_old_checks(KEEP_DAYS)
        if removed:
            logger.info("Pruned %s old checks (keeping %s days)", removed, KEEP_DAYS)
    except Exception as e:
        logger.warning("Prune failed, will retry on next check: %s", e)


def main():
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    validate_config()

    scheduler = BackgroundScheduler()
    scheduler.add_job(run_check, CronTrigger.from_crontab(CRON_SCHEDULE))
    scheduler.start()
    logger.info("Checker started with CRON_SCHEDULE=%s", CRON_SCHEDULE)

    if store.latest_check() is None:
        logger.info("No previous check stored, running initial check")
        scheduler.add_job(run_check)

    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
