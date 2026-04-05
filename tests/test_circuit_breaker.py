"""Tests for CircuitBreaker — covers CLOSED, OPEN, and HALF_OPEN states."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.services.circuit_breaker import CircuitBreaker

# ── Helpers ────────────────────────────────────────────────────────────────────


def _make_cb(**kwargs) -> CircuitBreaker:
    defaults = {"failure_threshold": 3, "recovery_timeout": 30.0, "name": "test"}
    defaults.update(kwargs)
    return CircuitBreaker(**defaults)


def _failing_fn() -> None:
    raise RuntimeError("boom")


def _ok_fn() -> str:
    return "ok"


# ── CLOSED state ───────────────────────────────────────────────────────────────


def test_closed_calls_through() -> None:
    cb = _make_cb()
    assert cb.state == CircuitBreaker.CLOSED
    result = cb.call(_ok_fn)
    assert result == "ok"


def test_closed_failure_increments_count() -> None:
    cb = _make_cb()
    cb.call(_failing_fn)
    assert cb.failure_count == 1
    assert cb.state == CircuitBreaker.CLOSED


def test_closed_resets_failure_count_on_success() -> None:
    cb = _make_cb()
    cb.call(_failing_fn)
    cb.call(_failing_fn)
    assert cb.failure_count == 2
    cb.call(_ok_fn)
    assert cb.failure_count == 0
    assert cb.state == CircuitBreaker.CLOSED


# ── OPEN state ─────────────────────────────────────────────────────────────────


def test_opens_after_threshold_failures() -> None:
    cb = _make_cb(failure_threshold=3)
    for _ in range(3):
        cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN


def test_open_fails_fast_returns_none() -> None:
    cb = _make_cb(failure_threshold=2)
    cb.call(_failing_fn)
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN

    mock = MagicMock(return_value="should not be called")
    result = cb.call(mock)
    assert result is None
    mock.assert_not_called()


def test_open_does_not_call_fn() -> None:
    cb = _make_cb(failure_threshold=1)
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN

    called = []
    cb.call(lambda: called.append(1))
    assert called == []


# ── HALF_OPEN state ────────────────────────────────────────────────────────────


def test_transitions_to_half_open_after_recovery_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    cb = _make_cb(failure_threshold=1, recovery_timeout=10.0)
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN

    # Simulate time passing beyond recovery_timeout
    monkeypatch.setattr(
        time,
        "monotonic",
        lambda: cb._opened_at + 11.0,  # type: ignore[operator]
    )

    # Next call transitions to HALF_OPEN and lets the call through
    result = cb.call(_ok_fn)
    assert result == "ok"
    assert cb.state == CircuitBreaker.CLOSED


def test_half_open_failure_reopens_circuit(monkeypatch: pytest.MonkeyPatch) -> None:
    cb = _make_cb(failure_threshold=1, recovery_timeout=10.0)
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN

    opened_at = cb._opened_at
    monkeypatch.setattr(time, "monotonic", lambda: opened_at + 11.0)  # type: ignore[operator]

    # Probe fails → go back to OPEN
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN


# ── Manual reset ───────────────────────────────────────────────────────────────


def test_manual_reset_clears_state() -> None:
    cb = _make_cb(failure_threshold=1)
    cb.call(_failing_fn)
    assert cb.state == CircuitBreaker.OPEN

    cb.reset()
    assert cb.state == CircuitBreaker.CLOSED
    assert cb.failure_count == 0


# ── Repr ───────────────────────────────────────────────────────────────────────


def test_repr_includes_state_and_name() -> None:
    cb = _make_cb(name="brapi")
    text = repr(cb)
    assert "brapi" in text
    assert "closed" in text
