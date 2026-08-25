import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta

logger = logging.getLogger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    status TEXT NOT NULL,
    alert_level REAL,
    station TEXT,
    breach_time TEXT,
    breach_value REAL,
    peak_value REAL,
    error TEXT
);

CREATE TABLE IF NOT EXISTS forecast_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    check_id INTEGER NOT NULL REFERENCES checks(id) ON DELETE CASCADE,
    sampled_at TEXT NOT NULL,
    value REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_samples_check ON forecast_samples(check_id);
"""

_DEFAULT_DB = os.path.join(os.getenv("DATA_DIR", "data"), "waterpijl.db")


def _to_dict(row):
    return dict(row) if row else None


class Store:
    """SQLite persistence for check results and forecast samples."""

    def __init__(self, db_path=None):
        self.db_path = db_path or os.getenv("DB_PATH", _DEFAULT_DB)
        parent = os.path.dirname(self.db_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(_SCHEMA)
        self._ensure_checks_peak_column()
        self.conn.commit()

    def _ensure_checks_peak_column(self):
        """Migrate pre-existing DBs that predate the peak_value column."""
        columns = [r["name"] for r in self.conn.execute("PRAGMA table_info(checks)")]
        if "peak_value" not in columns:
            self.conn.execute("ALTER TABLE checks ADD COLUMN peak_value REAL")

    def add_check(
        self, status, alert_level, station=None, breach_time=None, breach_value=None, peak_value=None, error=None,
        samples=None
    ):
        with self.conn:
            cur = self.conn.execute(
                "INSERT INTO checks"
                " (started_at, status, alert_level, station, breach_time, breach_value, peak_value, error)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (datetime.now(UTC).isoformat(), status, alert_level, station,
                 breach_time.isoformat() if breach_time else None,
                 float(breach_value) if breach_value is not None else None,
                 float(peak_value) if peak_value is not None else None,
                 error),
            )
            check_id = cur.lastrowid
            if samples:
                self.conn.executemany(
                    "INSERT INTO forecast_samples (check_id, sampled_at, value) VALUES (?, ?, ?)",
                    [(check_id, s["time"], float(s["value"])) for s in samples],
                )
        return check_id

    def latest_check(self):
        return _to_dict(self.conn.execute("SELECT * FROM checks ORDER BY id DESC LIMIT 1").fetchone())

    def check_history(self, limit=20):
        return [dict(r) for r in self.conn.execute(
            "SELECT * FROM checks ORDER BY id DESC LIMIT ?", (limit,)
        )]

    def forecast_samples(self, check_id):
        return [
            {"time": r["sampled_at"], "value": r["value"]}
            for r in self.conn.execute(
                "SELECT sampled_at, value FROM forecast_samples WHERE check_id = ? ORDER BY sampled_at", (check_id,)
            )
        ]

    def latest_with_samples(self):
        row = self.conn.execute(
            "SELECT c.* FROM checks c"
            " WHERE EXISTS (SELECT 1 FROM forecast_samples s WHERE s.check_id = c.id)"
            " ORDER BY c.id DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        result = dict(row)
        result["samples"] = self.forecast_samples(result["id"])
        return result

    def prune_old_checks(self, keep_days, cutoff=None):
        """Delete checks older than `keep_days`; their samples cascade away.

        Returns the number of checks removed and triggers a WAL checkpoint so
        the DB file actually shrinks."""
        cutoff = cutoff or (datetime.now(UTC) - timedelta(days=keep_days)).isoformat()
        try:
            with self.conn:
                cur = self.conn.execute("DELETE FROM checks WHERE started_at < ?", (cutoff,))
                removed = cur.rowcount
            if removed:
                # PASSIVE checkpoint never takes an exclusive lock, so it can't
                # conflict with the web process reading the same DB.
                self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")
        except sqlite3.OperationalError as e:
            logger.warning("Prune interrupted, will retry on next check: %s", e)
            return 0
        return removed

    def close(self):
        self.conn.close()


def default_db_path():
    return os.getenv("DB_PATH", _DEFAULT_DB)
