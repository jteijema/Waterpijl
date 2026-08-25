import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_format_dt_converts_to_amsterdam():
    import app

    assert "CEST" in app.format_dt("2026-08-27T06:30:00+02:00") or "2026-08-27 06:30" in app.format_dt(
        "2026-08-27T06:30:00+02:00"
    )
    assert "UTC" not in app.format_dt("2026-08-27T06:30:00+02:00")


def test_format_dt_naive_assumed_utc():
    import app

    assert "2026-08-27" in app.format_dt("2026-08-27T06:30:00Z")


def test_format_dt_invalid_returns_original():
    import app

    assert app.format_dt("not-a-date") == "not-a-date"


def test_write_status_is_atomic(tmp_path, monkeypatch):
    import app

    status_file = tmp_path / "status.json"
    monkeypatch.setattr(app, "STATUS_FILE", str(status_file))
    monkeypatch.setattr(app, "DATA_DIR", str(tmp_path))

    app.write_status(True, breach_time=datetime(2026, 8, 27))

    assert status_file.exists()
    assert not (tmp_path / "status.json.tmp").exists()
    data = json.loads(status_file.read_text())
    assert data["breached"] is True


def test_health_endpoint(tmp_path):
    import app

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    # Seed a plot so the startup check doesn't schedule a network fetch.
    (data_dir / "waterlevel_plot.png").write_bytes(b"png")

    old = (app.DATA_DIR, app.PLOT_PATH, app.STATUS_FILE)
    app.DATA_DIR = str(data_dir)
    app.PLOT_PATH = str(data_dir / "waterlevel_plot.png")
    app.STATUS_FILE = str(data_dir / "status.json")

    client = app.app.test_client()
    res = client.get("/health")
    assert res.status_code == 200
    assert res.get_json() == {"status": "ok"}

    app.DATA_DIR, app.PLOT_PATH, app.STATUS_FILE = old
