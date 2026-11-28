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
