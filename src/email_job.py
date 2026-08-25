import json
import logging
import os
import shutil
import uuid
from datetime import UTC, datetime

logger = logging.getLogger(__name__)

_DEFAULT_DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATA_DIR = os.getenv("DATA_DIR", _DEFAULT_DATA_DIR)
QUEUE_DIR = os.getenv("EMAIL_QUEUE_DIR", os.path.join(DATA_DIR, "queue"))


def enqueue_alert(breach_time, breach_value, plot_path=None, plot_bytes=None):
    """Write an alert email job into the shared queue dir for the email sidecar."""
    os.makedirs(QUEUE_DIR, exist_ok=True)
    job_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"

    job_file = os.path.join(QUEUE_DIR, f"alert-{job_id}.json")
    plot_copy = None
    if plot_bytes is not None:
        plot_copy = os.path.join(QUEUE_DIR, f"alert-{job_id}.png")
        with open(plot_copy, "wb") as f:
            f.write(plot_bytes)
        logger.info("Wrote plot to queue: %s", plot_copy)
    elif plot_path and os.path.exists(plot_path):
        plot_copy = os.path.join(QUEUE_DIR, f"alert-{job_id}.png")
        shutil.copy2(plot_path, plot_copy)
        logger.info("Copied plot to queue: %s", plot_copy)
    else:
        logger.warning("No plot provided, enqueueing alert without attachment")

    payload = {
        "job_id": job_id,
        "breach_time": breach_time.isoformat(),
        "breach_value": breach_value,
        "plot_path": plot_copy,
        "created_at": datetime.now(UTC).isoformat(),
    }
    tmp = job_file + ".tmp"
    with open(tmp, "w") as f:
        json.dump(payload, f)
    os.replace(tmp, job_file)
    logger.info("Enqueued alert email job %s into %s", job_id, QUEUE_DIR)
    return job_file
