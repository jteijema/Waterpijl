import pandas as pd
import pytest

import checker
import store


def _df(time_values):
    rows = [{"timeStamp": pd.Timestamp(t, tz="Europe/Amsterdam"), "value": v} for t, v in time_values]
    df = pd.DataFrame(rows)
    df["value"] = pd.to_numeric(df["value"]).round(2)
    return df[["timeStamp", "value"]]


@pytest.fixture
def rst(tmp_path, monkeypatch):
    s = store.Store(str(tmp_path / "queue.db"))
    monkeypatch.setattr(checker, "store", s)
    monkeypatch.setattr(checker, "ALERT_LEVEL", 200.0)
    return s


def test_ok_path_stores_check_no_email(rst, monkeypatch):
    df = _df([("2026-08-27T08:00", 150.0), ("2026-08-27T09:00", 180.0)])
    sent = []
    monkeypatch.setattr(checker, "fetch_forecast", lambda: (df, "Nederhemert"))
    monkeypatch.setattr(checker, "detect_breach", lambda df, lvl: (None, None))
    monkeypatch.setattr(checker, "enqueue_alert", lambda *a, **kw: sent.append(1))

    checker.run_check()

    check = rst.latest_check()
    assert check["status"] == "ok"
    assert check["station"] == "Nederhemert"
    assert check["peak_value"] == 180.0
    assert not sent
    assert len(rst.forecast_samples(check["id"])) == 2


def test_breach_path_enqueues_email(rst, monkeypatch):
    df = _df([("2026-08-27T08:00", 150.0), ("2026-08-27T09:00", 210.0)])
    breach = df.iloc[1]["timeStamp"], 210.0
    sent = []
    monkeypatch.setattr(checker, "fetch_forecast", lambda: (df, "Nederhemert"))
    monkeypatch.setattr(checker, "detect_breach", lambda df, lvl: breach)
    monkeypatch.setattr(checker, "enqueue_alert", lambda *a, **kw: sent.append((a, kw)))

    checker.run_check()

    check = rst.latest_check()
    assert check["status"] == "breach"
    assert check["breach_value"] == 210.0
    assert len(sent) == 1
    assert sent[0][1].get("plot_bytes") is not None


def test_error_path_records_error_no_email(rst, monkeypatch):
    def boom():
        raise ValueError("API down")

    monkeypatch.setattr(checker, "fetch_forecast", boom)
    monkeypatch.setattr(checker, "enqueue_alert", lambda *a, **kw: None)

    checker.run_check()

    check = rst.latest_check()
    assert check["status"] == "error"
    assert "API down" in check["error"]
    assert len(rst.forecast_samples(check["id"])) == 0
