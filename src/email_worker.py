import json
import logging
import os
import smtplib
import sys
import time
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.getenv("DATA_DIR", os.path.join(REPO_ROOT, "data"))
QUEUE_DIR = os.getenv("EMAIL_QUEUE_DIR", os.path.join(DATA_DIR, "queue"))
EMAIL_TEMPLATE_FILE = os.getenv("EMAIL_TEMPLATE_FILE", os.path.join(REPO_ROOT, "email_template.txt"))

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASS = os.getenv("EMAIL_PASS")
EMAIL_TO   = os.getenv("EMAIL_TO", EMAIL_USER)

POLL_INTERVAL = float(os.getenv("EMAIL_POLL_INTERVAL", "10"))
MAX_ATTEMPTS  = int(os.getenv("EMAIL_MAX_ATTEMPTS", "10"))
BASE_BACKOFF_S = float(os.getenv("EMAIL_BACKOFF_BASE", "30"))
MAX_BACKOFF_S  = 3600

_env = Environment(loader=FileSystemLoader(os.path.dirname(EMAIL_TEMPLATE_FILE)))
_template = _env.get_template(os.path.basename(EMAIL_TEMPLATE_FILE))


def render_email(breach_time, breach_value):
    """Render the Jinja template into (subject, body). Expects a 'Subject:' line first."""
    rendered = _template.render(breach_time=breach_time, breach_value=breach_value)
    subject, _, body = rendered.partition("\n\n")
    subject = subject.partition(":")[2].strip()
    return subject, body


def send_email(subject, body, plot_path):
    msg = EmailMessage()
    msg.set_content(body)
    msg["Subject"] = subject
    msg["From"] = f"Watermelder <{EMAIL_USER}>"
    msg["To"] = EMAIL_TO

    if plot_path and os.path.exists(plot_path):
        with open(plot_path, "rb") as f:
            msg.add_attachment(f.read(), maintype="image", subtype="png", filename=os.path.basename(plot_path))
        logger.info("Attached plot from %s", plot_path)
    else:
        logger.warning("No plot attachment found at %s", plot_path)

    logger.info("Sending alert email to %s", EMAIL_TO)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_USER, EMAIL_PASS)
        server.send_message(msg)
    logger.info("Alert email sent")


def _write_job(job_file, job):
    tmp = job_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(job, f)
    os.replace(tmp, job_file)


def _next_retry(attempts):
    backoff = min(BASE_BACKOFF_S * (2 ** (attempts - 1)), MAX_BACKOFF_S)
    return datetime.now(UTC) + timedelta(seconds=backoff)


def list_jobs():
    return [
        f
        for f in os.listdir(QUEUE_DIR)
        if f.endswith(".json") and not f.endswith(".failed.json")
    ] if os.path.isdir(QUEUE_DIR) else []


def process_job(file_path):
    file_path = str(file_path)
    with open(file_path) as f:
        job = json.load(f)

    next_retry = job.get("next_retry")
    if next_retry:
        when = datetime.fromisoformat(next_retry)
        if when > datetime.now(UTC):
            return 0

    attempts = job.get("attempts", 0)
    try:
        breach_time = datetime.fromisoformat(job["breach_time"])
        subject, body = render_email(breach_time, job["breach_value"])
        send_email(subject, body, job.get("plot_path"))
        for path in (file_path, job.get("plot_path")):
            if path and os.path.exists(path):
                os.unlink(path)
        logger.info("Processed and removed job %s", job.get("job_id"))
        return 0
    except (KeyError, ValueError):
        logger.exception("Invalid job file %s, marking failed", file_path)
        os.rename(file_path, file_path.replace(".json", ".failed.json"))
        return -1
    except Exception as e:
        attempts += 1
        job["attempts"] = attempts
        job["last_error"] = str(e)
        if attempts >= MAX_ATTEMPTS:
            os.rename(file_path, file_path.replace(".json", ".failed.json"))
            logger.error("Job %s exhausted %d attempts, marked failed: %s", job.get("job_id"), MAX_ATTEMPTS, e)
            return -1
        job["next_retry"] = _next_retry(attempts).isoformat()
        _write_job(file_path, job)
        logger.warning("Job %s attempt %d failed, retrying: %s", job.get("job_id"), attempts, e)
        return 1


def main():
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logger = logging.getLogger("email_worker")

    if not EMAIL_USER or not EMAIL_PASS:
        logger.error("EMAIL_USER and EMAIL_PASS must be set to send emails")
        sys.exit(1)
    os.makedirs(QUEUE_DIR, exist_ok=True)

    logger.info(
        "Email worker polling %s every %.0fs (to=%s, max_attempts=%d)",
        QUEUE_DIR, POLL_INTERVAL, EMAIL_TO, MAX_ATTEMPTS,
    )
    while True:
        try:
            for name in sorted(list_jobs()):
                process_job(os.path.join(QUEUE_DIR, name))
        except Exception:
            logger.exception("Unhandled error in poll loop")
        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
