"""
circuit_breaker.py — Lightweight circuit breaker for external HTTP integrations.

States
------
CLOSED    Normal operation. Calls pass through to the wrapped function.
OPEN      Service presumed unavailable. Calls fail fast without hitting the
          remote endpoint. Transitions to HALF_OPEN after recovery_timeout.
HALF_OPEN Recovery probe. One call is allowed through; success → CLOSED,
          failure → OPEN (reset timer).

Usage
-----
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=30)

    result = cb.call(my_http_function, arg1, kwarg=v)
    # Returns None when the circuit is OPEN (fail-fast, no exception raised).
    # The caller decides how to handle None (return cached data, raise, etc.).
"""

from __future__ import annotations

import threading
import time
from typing import Any, Callable


class CircuitBreaker:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        *,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0,
        name: str = "unnamed",
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._name = name

        self._state = self.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────────

    @property
    def state(self) -> str:
        return self._state

    @property
    def failure_count(self) -> int:
        return self._failure_count

    def call(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """Execute *fn* with circuit-breaker protection.

        Returns ``None`` immediately when the circuit is OPEN so callers can
        apply a stale-cache fallback without catching exceptions.
        """
        with self._lock:
            if self._state == self.OPEN:
                elapsed = time.monotonic() - (self._opened_at or 0.0)
                if elapsed >= self._recovery_timeout:
                    self._state = self.HALF_OPEN
                else:
                    return None  # fail fast

        try:
            result = fn(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            return None

    def reset(self) -> None:
        """Manually reset the circuit to CLOSED (useful for tests)."""
        with self._lock:
            self._do_reset()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _on_success(self) -> None:
        with self._lock:
            self._do_reset()

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = self.OPEN
                self._opened_at = time.monotonic()

    def _do_reset(self) -> None:
        self._state = self.CLOSED
        self._failure_count = 0
        self._opened_at = None

    def __repr__(self) -> str:
        return (
            f"CircuitBreaker(name={self._name!r}, state={self._state}, "
            f"failures={self._failure_count}/{self._failure_threshold})"
        )
