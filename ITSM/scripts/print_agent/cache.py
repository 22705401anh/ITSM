"""
KOSTAL Print Agent — Local SQLite Cache for Offline Resilience

Caches print jobs locally when the backend API is unreachable.
Flushes cached jobs on reconnection.
"""
import sqlite3
import json
import os
import logging
from datetime import datetime

logger = logging.getLogger("KostalPrintAgent")


class LocalCache:
    """SQLite-backed local queue for offline job caching."""

    def __init__(self, db_path: str = "./cache.db"):
        self.db_path = db_path
        self._ensure_db()

    def _ensure_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT UNIQUE NOT NULL,
                    job_data TEXT NOT NULL,
                    cached_at TEXT NOT NULL,
                    retries INTEGER DEFAULT 0,
                    last_retry TEXT
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS cached_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correlation_id TEXT NOT NULL,
                    event_data TEXT NOT NULL,
                    cached_at TEXT NOT NULL
                )
            """)
            conn.commit()

    def cache_job(self, correlation_id: str, job_dict: dict):
        """Store a job for later submission."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO cached_jobs (correlation_id, job_data, cached_at) VALUES (?, ?, ?)",
                    (correlation_id, json.dumps(job_dict, default=str), datetime.utcnow().isoformat()),
                )
                conn.commit()
            logger.debug(f"Cached job {correlation_id}")
        except Exception as e:
            logger.error(f"Failed to cache job: {e}")

    def cache_event(self, correlation_id: str, event_dict: dict):
        """Store an event for later submission."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "INSERT INTO cached_events (correlation_id, event_data, cached_at) VALUES (?, ?, ?)",
                    (correlation_id, json.dumps(event_dict, default=str), datetime.utcnow().isoformat()),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Failed to cache event: {e}")

    def get_pending_jobs(self, limit: int = 500) -> list:
        """Retrieve cached jobs for flush."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, correlation_id, job_data FROM cached_jobs ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"cache_id": r[0], "correlation_id": r[1], "data": json.loads(r[2])} for r in rows]

    def get_pending_events(self, limit: int = 500) -> list:
        """Retrieve cached events for flush."""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, correlation_id, event_data FROM cached_events ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"cache_id": r[0], "correlation_id": r[1], "data": json.loads(r[2])} for r in rows]

    def remove_jobs(self, cache_ids: list):
        """Remove successfully submitted jobs from cache."""
        if not cache_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(cache_ids))
            conn.execute(f"DELETE FROM cached_jobs WHERE id IN ({placeholders})", cache_ids)
            conn.commit()

    def remove_events(self, cache_ids: list):
        if not cache_ids:
            return
        with sqlite3.connect(self.db_path) as conn:
            placeholders = ",".join("?" * len(cache_ids))
            conn.execute(f"DELETE FROM cached_events WHERE id IN ({placeholders})", cache_ids)
            conn.commit()

    @property
    def pending_count(self) -> int:
        with sqlite3.connect(self.db_path) as conn:
            return conn.execute("SELECT COUNT(*) FROM cached_jobs").fetchone()[0]
