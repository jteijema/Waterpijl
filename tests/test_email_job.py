from datetime import datetime, timedelta, timezone

import email_job


def _set_queue(monkeypatch, queue_dir):
    monkeypatch.setattr(email_job, "QUEUE_DIR", str(queue_dir))


def test_enqueue_alert_writes_atomic_job_and_copies_plot(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _set_queue(monkeypatch, queue)
    plot = tmp_path / "waterlevel_plot.png"
    plot.write_bytes(b"fake-png")

    breach_time = datetime(2026, 8, 27, 6, 30, tzinfo=timezone(timedelta(hours=2)))

    job_file = email_job.enqueue_alert(breach_time, 370.21, str(plot))

    assert job_file.startswith(str(queue))
    assert job_file.endswith(".json")
    assert not list(queue.glob("*.tmp"))

    jobs = list(queue.glob("alert-*.json"))
    plots = list(queue.glob("alert-*.png"))
    assert len(jobs) == 1
    assert len(plots) == 1
    assert plots[0].read_bytes() == b"fake-png"

    payload = __import__("json").loads(jobs[0].read_text())
    assert payload["breach_value"] == 370.21
    assert payload["breach_time"] == breach_time.isoformat()
    assert payload["plot_path"] == str(plots[0])
    assert payload["job_id"]


def test_enqueue_alert_without_plot_still_creates_job(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _set_queue(monkeypatch, queue)
    breach_time = datetime(2026, 8, 27, 6, 30, tzinfo=timezone(timedelta(hours=2)))

    job_file = email_job.enqueue_alert(breach_time, 250.0, None)

    assert job_file.endswith(".json")
    assert list(queue.glob("alert-*.json"))
    assert list(queue.glob("alert-*.png")) == []
