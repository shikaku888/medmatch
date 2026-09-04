"""Process-shared request rate limiting backed by a small SQLite file."""
from __future__ import annotations

import os
import sqlite3
import time
from pathlib import Path
from threading import Lock


class RateLimitUnavailable(RuntimeError):
    """Raised when the configured shared rate-limit store cannot be used."""


class RateLimiter:
    def __init__(self, path: Path | None = None) -> None:
        configured = path or os.environ.get("RATE_LIMIT_DB")
        if configured:
            self.path = Path(configured)
        else:
            data_dir = os.environ.get("SCANNER_DATA_DIR")
            self.path = (
                Path(data_dir).parent / "rate-limit.db"
                if data_dir
                else Path(__file__).resolve().parent / "data" / "rate-limit.db"
            )
        self._schema_lock = Lock()
        self._schema_ready = False

    def _ensure_schema(self) -> None:
        if self._schema_ready:
            return
        with self._schema_lock:
            if self._schema_ready:
                return
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(self.path, timeout=1.0) as conn:
                    conn.execute("PRAGMA busy_timeout=1000")
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS rate_limit_events ("
                        "bucket TEXT NOT NULL, event_at REAL NOT NULL)"
                    )
                    conn.execute(
                        "CREATE INDEX IF NOT EXISTS idx_rate_limit_events_bucket_time "
                        "ON rate_limit_events(bucket, event_at)"
                    )
                self._schema_ready = True
            except (OSError, sqlite3.Error) as exc:
                raise RateLimitUnavailable(str(self.path)) from exc

    def allow(self, bucket: str, limit: int, window_seconds: float) -> bool:
        now = time.time()
        cutoff = now - window_seconds
        try:
            self._ensure_schema()
            with sqlite3.connect(self.path, timeout=1.0) as conn:
                conn.execute("PRAGMA busy_timeout=1000")
                conn.execute("BEGIN IMMEDIATE")
                conn.execute(
                    "DELETE FROM rate_limit_events "
                    "WHERE bucket = ? AND event_at < ?",
                    (bucket, cutoff),
                )
                count = conn.execute(
                    "SELECT COUNT(*) FROM rate_limit_events WHERE bucket = ?",
                    (bucket,),
                ).fetchone()[0]
                if count >= limit:
                    conn.rollback()
                    return False
                conn.execute(
                    "INSERT INTO rate_limit_events(bucket, event_at) VALUES (?, ?)",
                    (bucket, now),
                )
                conn.commit()
                return True
        except (OSError, sqlite3.Error) as exc:
            raise RateLimitUnavailable(str(self.path)) from exc


rate_limiter = RateLimiter()
