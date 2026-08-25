
import pytest

import store


@pytest.fixture
def rst(tmp_path):
    s = store.Store(str(tmp_path / "test.db"))
    yield s
    s.close()


def test_empty_db_has_no_checks(rst):
    assert rst.latest_check() is None
    assert rst.latest_with_samples() is None


def test_add_and_read_check(rst):
    cid = rst.add_check(status="ok", alert_level=200.0, station="Nederhemert")
    check = rst.latest_check()
    assert check["id"] == cid
    assert check["status"] == "ok"
    assert check["station"] == "Nederhemert"
    assert check["breach_time"] is None
    assert check["breach_value"] is None
    assert check["error"] is None


def test_latest_is_most_recent(rst):
    rst.add_check(status="ok", alert_level=200)
    cid2 = rst.add_check(status="breach", alert_level=200, breach_value=210.0)
    assert rst.latest_check()["id"] == cid2
    assert rst.latest_check()["status"] == "breach"


def test_samples_round_trip(rst):
    samples = [{"time": "2026-08-27T08:00:00+02:00", "value": 150.0},
               {"time": "2026-08-27T09:00:00+02:00", "value": 210.0}]
    cid = rst.add_check(status="breach", alert_level=200, breach_value=210.0, samples=samples)
    got = rst.forecast_samples(cid)
    assert len(got) == 2
    assert got[1]["value"] == 210.0
    assert got[0]["time"] == "2026-08-27T08:00:00+02:00"


def test_latest_with_samples_skips_empty_checks(rst):
    rst.add_check(status="error", alert_level=200, error="boom")
    cid = rst.add_check(status="ok", alert_level=200, samples=[{"time": "2026-08-27", "value": 1.0}])
    latest = rst.latest_with_samples()
    assert latest["id"] == cid
    assert len(latest["samples"]) == 1


def test_peak_value_stored(rst):
    rst.add_check(status="ok", alert_level=200, peak_value=187.5, samples=[{"time": "2026-08-27", "value": 187.5}])
    check = rst.latest_check()
    assert check["peak_value"] == 187.5


def test_migrates_legacy_db_without_peak_column(tmp_path):
    import sqlite3

    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute(
        "CREATE TABLE checks (id INTEGER PRIMARY KEY AUTOINCREMENT, started_at TEXT NOT NULL,"
        " status TEXT NOT NULL, alert_level REAL, station TEXT, breach_time TEXT, breach_value REAL, error TEXT)"
    )
    conn.execute("CREATE TABLE forecast_samples (id INTEGER PRIMARY KEY AUTOINCREMENT, check_id INTEGER NOT NULL,"
                 " sampled_at TEXT NOT NULL, value REAL NOT NULL)")
    conn.commit()
    conn.close()

    s = store.Store(str(db))
    try:
        s.add_check(status="ok", alert_level=200, peak_value=190.0)
        assert s.latest_check()["peak_value"] == 190.0
    finally:
        s.close()


def test_prune_removes_old_checks_only(rst):
    from datetime import UTC, datetime, timedelta

    now = datetime.now(UTC)
    recent_id = rst.add_check(status="ok", alert_level=200, samples=[{"time": "2026-08-27", "value": 1.0}])
    old_id = rst.add_check(status="ok", alert_level=200, samples=[{"time": "2026-08-01", "value": 1.0}])

    with rst.conn:
        rst.conn.execute("UPDATE checks SET started_at = ? WHERE id = ?",
                         ((now - timedelta(days=120)).isoformat(), old_id))

    removed = rst.prune_old_checks(60, cutoff=(now - timedelta(days=60)).isoformat())

    assert removed == 1
    assert rst.latest_check()["id"] == recent_id
    assert not [c for c in rst.check_history(100) if c["id"] == old_id]
