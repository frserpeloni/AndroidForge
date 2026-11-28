"""Limitador de janela deslizante para endpoints de pareamento."""
from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable


class SlidingWindowRateLimiter:
    def __init__(
        self,
        limit: int = 8,
        window_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit deve ser inteiro positivo")
        if window_seconds <= 0:
            raise ValueError("window_seconds deve ser positivo")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._clock = clock
        self._events: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        if not isinstance(key, str) or not key:
            raise ValueError("key deve ser uma string não vazia")
        now = self._clock()
        cutoff = now - self.window_seconds
        with self._lock:
            expired_keys = []
            for current_key, events in self._events.items():
                while events and events[0] <= cutoff:
                    events.popleft()
                if not events:
                    expired_keys.append(current_key)
            for current_key in expired_keys:
                self._events.pop(current_key, None)

            events = self._events.setdefault(key, deque())
            if len(events) >= self.limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        """Limpa contadores, destinado a reinicialização controlada e testes."""
        with self._lock:
            self._events.clear()


class SQLiteSlidingWindowRateLimiter:
    """Limitador persistente e atômico entre threads, processos e reinicializações."""

    def __init__(
        self,
        limit: int = 8,
        window_seconds: float = 60.0,
        *,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise ValueError("limit deve ser inteiro positivo")
        if window_seconds <= 0:
            raise ValueError("window_seconds deve ser positivo")
        self.limit = limit
        self.window_seconds = float(window_seconds)
        self._clock = clock

    def allow(self, key: str, db_path: str) -> bool:
        if not isinstance(key, str) or not key:
            raise ValueError("key deve ser uma string não vazia")
        from pathlib import Path
        import sqlite3

        path = Path(db_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        now = self._clock()
        cutoff = now - self.window_seconds
        conn = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        try:
            conn.execute("PRAGMA busy_timeout = 10000")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pairing_rate_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    bucket TEXT NOT NULL,
                    occurred_at REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_pairing_rate_bucket_time
                ON pairing_rate_events(bucket, occurred_at)
            """)
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("DELETE FROM pairing_rate_events WHERE occurred_at <= ?", (cutoff,))
            row = conn.execute(
                "SELECT COUNT(*) FROM pairing_rate_events WHERE bucket = ? AND occurred_at > ?",
                (key, cutoff),
            ).fetchone()
            if row[0] >= self.limit:
                conn.rollback()
                return False
            conn.execute(
                "INSERT INTO pairing_rate_events(bucket, occurred_at) VALUES (?, ?)",
                (key, now),
            )
            conn.commit()
            return True
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
