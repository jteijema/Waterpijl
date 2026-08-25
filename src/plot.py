import io

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def render_forecast_plot(samples, alert_level, station=None):
    """Render a forecast plot to PNG bytes. `samples` is a list of {'time': str, 'value': float}."""
    df = pd.DataFrame(samples)
    df["time"] = pd.to_datetime(df["time"])

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(df["time"], df["value"], label="Water Level (cm)", color="blue")
    ax.axhline(y=alert_level, color="red", linestyle="--", label=f"Alert level ({alert_level} cm)")
    ax.set_title(f"Water Level Forecast: {station or 'unknown'}")
    ax.set_xlabel("Date")
    ax.set_ylabel("Water Level (cm +NAP)")
    ax.legend()
    ax.grid(True)
    plt.setp(ax.get_xticklabels(), rotation=45, ha="right")
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()


def render_history_plot(checks, alert_level):
    """Bar chart of peak forecast level per check. `checks` is a list of dicts
    with keys started_at, peak_value (may be None), status."""
    frame = [
        {"started_at": c["started_at"], "peak_value": c.get("peak_value"), "status": c.get("status")}
        for c in checks
    ]
    df = pd.DataFrame(frame)
    if df.empty:
        df = pd.DataFrame({"started_at": [], "peak_value": [], "status": []})
    df["started_at"] = pd.to_datetime(df["started_at"], utc=True)
    df = df.sort_values("started_at")

    colors = []
    for status in df["status"]:
        if status == "breach":
            colors.append("#c53030")
        elif status == "error":
            colors.append("#d69e2e")
        else:
            colors.append("#2b6cb0")

    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.bar(df["started_at"], df["peak_value"].fillna(0), width=0.6, color=colors)
    ax.axhline(y=alert_level, color="red", linestyle="--", lw=1.2,
               label=f"Alert level ({alert_level} cm)")
    ax.set_title("Peak forecast level per check")
    ax.set_ylabel("cm +NAP")
    ax.legend(loc="upper left")
    ax.grid(True, axis="y", alpha=0.3)
    fig.tight_layout()

    buf = io.BytesIO()
    fig.savefig(buf, format="png")
    plt.close(fig)
    return buf.getvalue()
