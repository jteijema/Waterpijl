from datetime import UTC, datetime
from unittest import mock

import pytest

import waterlevel


def _payload(events, name="Nederhemert"):
    return {
        "results": [
            {
                "events": events,
                "location": {"properties": {"locationName": name}},
            }
        ]
    }


def _event(iso_time, value):
    return {"timeStamp": iso_time, "value": value}


def _fetch(payload):
    with mock.patch("waterlevel.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = payload
        return waterlevel.fetch_forecast()


def test_fetch_returns_events_in_amsterdam_tz():
    payload = _payload([_event("2026-08-27T04:00:00Z", 150.0)])
    df, station = _fetch(payload)
    assert station == "Nederhemert"
    assert df["timeStamp"].dt.tz is not None
    assert str(df["timeStamp"].dt.tz) == "Europe/Amsterdam"
    assert float(df.iloc[0]["value"]) == 150.0


def test_fetch_empty_payload_raises():
    with mock.patch("waterlevel.requests.get") as get:
        get.return_value.status_code = 200
        get.return_value.json.return_value = {"results": []}
        with pytest.raises(ValueError, match="No valid data"):
            waterlevel.fetch_forecast()


def test_detect_breach_returns_first():
    payload = _payload([
        _event("2026-08-27T04:00:00Z", 150.0),
        _event("2026-08-27T06:00:00Z", 210.0),
        _event("2026-08-27T08:00:00Z", 245.0),
    ])
    df, _ = _fetch(payload)
    when, value = waterlevel.detect_breach(df, 200.0)
    assert value == 210.0
    assert when.hour == 8  # 06:00 UTC = 08:00 Europe/Amsterdam


def test_detect_breach_none_when_safe():
    payload = _payload([_event("2026-08-27T04:00:00Z", 150.0), _event("2026-08-27T06:00:00Z", 180.0)])
    df, _ = _fetch(payload)
    assert waterlevel.detect_breach(df, 200.0) == (None, None)


def test_url_has_no_double_ampersand():
    url = waterlevel.get_waterlevel_url(datetime(2026, 8, 26, tzinfo=UTC))
    assert "&&" not in url
    assert "locationCode=" in url
    assert "startTime=" in url
