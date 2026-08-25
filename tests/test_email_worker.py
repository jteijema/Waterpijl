import json
from datetime import UTC, datetime, timedelta, timezone

import pytest

import email_worker


@pytest.fixture
def queue(tmp_path):
    q = tmp_path / "queue"
    q.mkdir()
    return q


def _reset_queue(monkeypatch, queue):
    monkeypatch.setattr(email_worker, "QUEUE_DIR", str(queue))


def _make_job(queue, plot_bytes=b"fake-png", breach_value=370.21):
    plot = queue / "alert-plot.png"
    plot.write_bytes(plot_bytes)
    job = {
        "job_id": "abc123",
        "breach_time": "2026-08-27T06:30:00+02:00",
        "breach_value": breach_value,
        "plot_path": str(plot),
        "created_at": "2026-08-25T23:00:00+00:00",
    }
    path = queue / "alert-abc123.json"
    path.write_text(json.dumps(job))
    return path


def test_process_job_success(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _reset_queue(monkeypatch, queue)
    path = _make_job(queue)

    sent = {}
    def fake_send(subject, body, plot_path):
        sent.update(subject=subject, body=body, plot_path=plot_path)
    monkeypatch.setattr(email_worker, "send_email", fake_send)

    assert email_worker.process_job(path) == 0
    assert sent["subject"] == "Waterpeil Alarm: 370cm om 06:30"
    assert sent["plot_path"].endswith(".png")
    assert "waterpeil" not in sent["body"].lower() or "Waterstand alarm!" in sent["body"]
    assert not list(queue.glob("alert-*.json"))
    assert not list(queue.glob("alert-*.png"))


def test_render_email_subject_and_body():
    breach_time = datetime(2026, 8, 27, 6, 30, tzinfo=timezone(timedelta(hours=2)))
    subject, body = email_worker.render_email(breach_time, 370.21)
    assert subject == "Waterpeil Alarm: 370cm om 06:30"
    assert "370.21 cm +NAP" in body
    assert "2026-08-27" in body


def test_send_failure_schedules_retry(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _reset_queue(monkeypatch, queue)
    path = _make_job(queue)

    def boom(*args, **kwargs):
        raise ConnectionError("SMTP down")
    monkeypatch.setattr(email_worker, "send_email", boom)

    assert email_worker.process_job(path) == 1
    job = json.loads(path.read_text())
    assert job["attempts"] == 1
    assert "next_retry" in job
    assert "SMTP down" in job["last_error"]
    assert str(path).endswith(".json")


def test_send_failure_exhausts_to_failed(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _reset_queue(monkeypatch, queue)
    path = _make_job(queue)

    def boom(*args, **kwargs):
        raise ConnectionError("SMTP down")
    monkeypatch.setattr(email_worker, "send_email", boom)
    monkeypatch.setattr(email_worker, "MAX_ATTEMPTS", 2)
    monkeypatch.setattr(
        email_worker, "_next_retry", lambda attempts: datetime.now(UTC) - timedelta(minutes=1)
    )

    assert email_worker.process_job(path) == 1
    assert email_worker.process_job(path) == -1
    assert list(queue.glob("alert-abc123.failed.json"))
    assert not list(queue.glob("alert-abc123.json"))


def test_invalid_job_marked_failed(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _reset_queue(monkeypatch, queue)
    path = queue / "alert-bad.json"
    path.write_text(json.dumps({"job_id": "bad"}))

    assert email_worker.process_job(str(path)) == -1
    assert list(queue.glob("alert-bad.failed.json"))


def test_job_pending_retry_is_skipped(tmp_path, monkeypatch):
    queue = tmp_path / "queue"
    queue.mkdir(exist_ok=True)
    _reset_queue(monkeypatch, queue)
    path = _make_job(queue)

    job = json.loads(path.read_text())
    job["attempts"] = 1
    job["next_retry"] = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    path.write_text(json.dumps(job))

    assert email_worker.process_job(path) == 0  # skipped, no side effects
    assert list(queue.glob("alert-abc123.json"))
