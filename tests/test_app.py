import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def _seed_store(tmp_path):
    import app
    import store

    db = tmp_path / "app.db"
    rst = store.Store(str(db))
    samples = [
        {"time": "2026-08-27T08:00:00+02:00", "value": 150.0},
        {"time": "2026-08-27T09:00:00+02:00", "value": 210.0},
    ]
    rst.add_check(status="breach", alert_level=200.0, station="Nederhemert",
                  breach_value=210.0, peak_value=210.0, samples=samples)

    orig = (app._store, app.DATABASE_PATH)
    app._store = rst
    app.DATABASE_PATH = str(db)
    app._plot_cache.clear()
    client = app.app.test_client()
    return client, rst, orig


def _restore(app, rst, orig):
    rst.close()
    app._store, app.DATABASE_PATH = orig


def test_health(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/health")
        assert res.status_code == 200
        assert res.get_json() == {"status": "ok"}
    finally:
        _restore(app, rst, orig)


def test_index_shows_latest_check(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/")
        assert res.status_code == 200
        html = res.get_data(as_text=True)
        assert "matroos.AF_234.00" in html  # configured location code
        assert "Alert level exceeded" in html
    finally:
        _restore(app, rst, orig)


def test_api_status(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/api/status")
        body = res.get_json()
        assert body["status"] == "breach"
        assert body["breach_value"] == 210.0
        assert body["station"] == "Nederhemert"
    finally:
        _restore(app, rst, orig)


def test_api_status_empty_db(tmp_path, monkeypatch):
    import app
    import store

    db = tmp_path / "empty.db"
    rst = store.Store(str(db))
    orig = (app._store, app.DATABASE_PATH)
    app._store, app.DATABASE_PATH = rst, str(db)
    try:
        res = app.app.test_client().get("/api/status")
        assert res.get_json() == {"status": "unknown", "has_data": False}
    finally:
        rst.close()
        app._store, app.DATABASE_PATH = orig


def test_api_forecast(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/api/forecast")
        body = res.get_json()
        assert body["status"] == "breach"
        assert len(body["samples"]) == 2
        assert body["samples"][1]["value"] == 210.0
    finally:
        _restore(app, rst, orig)


def test_plot_serves_png(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/plot.png")
        assert res.status_code == 200
        assert res.mimetype == "image/png"
        assert res.data.startswith(b"\x89PNG")
    finally:
        _restore(app, rst, orig)


def test_plot_empty_is_404(tmp_path, monkeypatch):
    import app
    import store

    db = tmp_path / "empty.db"
    rst = store.Store(str(db))
    orig = (app._store, app.DATABASE_PATH)
    app._store, app.DATABASE_PATH = rst, str(db)
    try:
        res = app.app.test_client().get("/plot.png")
        assert res.status_code == 404
    finally:
        rst.close()
        app._store, app.DATABASE_PATH = orig


def test_history_plot_serves_png(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        res = client.get("/plot/history.png")
        assert res.status_code == 200
        assert res.mimetype == "image/png"
        assert res.data.startswith(b"\x89PNG")
    finally:
        _restore(app, rst, orig)


def test_index_shows_recent_checks(tmp_path):
    import app

    client, rst, orig = _seed_store(tmp_path)
    try:
        html = client.get("/").get_data(as_text=True)
        assert "Recent checks" in html
        assert "Peak per check" in html
    finally:
        _restore(app, rst, orig)


def test_format_dt_amsterdam():
    import app

    s = app.format_dt("2026-08-27T06:30:00+02:00")
    assert "2026-08-27 06:30" in s
    assert "UTC" not in s


def test_format_dt_invalid_returns_original():
    import app

    assert app.format_dt("not-a-date") == "not-a-date"
