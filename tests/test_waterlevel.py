from datetime import UTC, datetime
from unittest import mock

import pytest

import waterlevel


def _payload(events):
    return {
        "results": [
            {
                "events": events,
                "location": {"properties": {"locationName": "Nederhemert"}},
            }
        ]
    }


def _event(iso_time, value):
    return {"timeStamp": iso_time, "value": value}


def _assert_fetch(alert_level, payload, plot_path):
    with mock.patch("waterlevel.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = payload
        return waterlevel.fetch_process_and_plot(alert_level, plot_path)


def test_fetch_returns_first_breach(tmp_path):
    payload = _payload(
        [
            _event("2026-08-27T04:00:00Z", 150.0),
            _event("2026-08-27T06:00:00Z", 210.0),
            _event("2026-08-27T08:00:00Z", 245.0),
        ]
    )
    plot = tmp_path / "plot.png"
    breach_time, breach_value = _assert_fetch(200.0, payload, plot)
    assert breach_value == 210.0
    assert breach_time.hour == 8  # 06:00 UTC = 08:00 Europe/Amsterdam
    assert plot.exists()


def test_no_breach_returns_none(tmp_path):
    payload = _payload(
        [
            _event("2026-08-27T04:00:00Z", 150.0),
            _event("2026-08-27T06:00:00Z", 180.0),
        ]
    )
    plot = tmp_path / "plot.png"
    breach_time, breach_value = _assert_fetch(200.0, payload, plot)
    assert breach_time is None
    assert breach_value is None


def test_empty_response_raises(tmp_path):
    plot = tmp_path / "plot.png"
    with mock.patch("waterlevel.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"results": []}
        with pytest.raises(ValueError, match="No valid data"):
            waterlevel.fetch_process_and_plot(200.0, plot)


def test_url_has_no_double_ampersand():
    url = waterlevel.get_waterlevel_url(datetime(2026, 8, 26, tzinfo=UTC))
    assert "&&" not in url
    assert "locationCode=" in url
    assert "startTime=" in url
