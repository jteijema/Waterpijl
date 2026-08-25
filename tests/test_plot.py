import plot


def test_render_forecast_plot_returns_png():
    samples = [
        {"time": "2026-08-27T08:00:00+02:00", "value": 150.0},
        {"time": "2026-08-27T09:00:00+02:00", "value": 210.0},
    ]
    png = plot.render_forecast_plot(samples, 200.0, "Nederhemert")
    assert png.startswith(b"\x89PNG")
    assert len(png) > 1000


def test_render_history_plot_png():
    checks = [
        {"started_at": "2026-08-25T06:00:00+02:00", "peak_value": 150.0, "status": "ok"},
        {"started_at": "2026-08-25T18:00:00+02:00", "peak_value": 210.0, "status": "breach"},
        {"started_at": "2026-08-26T06:00:00+02:00", "peak_value": 165.0, "status": "ok"},
    ]
    png = plot.render_history_plot(checks, 200.0)
    assert png.startswith(b"\x89PNG")
