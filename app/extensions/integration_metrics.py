from __future__ import annotations

import threading
from collections import Counter
from typing import Any

_lock = threading.Lock()
_counters: Counter[str] = Counter()


def increment_metric(name: str, amount: int = 1) -> None:
    if amount <= 0:
        return
    with _lock:
        _counters[name] += amount


def snapshot_metrics(prefix: str | None = None) -> dict[str, int]:
    with _lock:
        raw = dict(_counters)
    if prefix is None:
        return raw
    return {key: value for key, value in raw.items() if key.startswith(prefix)}


def reset_metrics_for_tests() -> None:
    with _lock:
        _counters.clear()


def build_brapi_metrics_payload() -> dict[str, Any]:
    metrics = snapshot_metrics(prefix="brapi.")
    return {
        "provider": "brapi",
        "counters": metrics,
        "summary": {
            "timeouts": metrics.get("brapi.timeout", 0),
            "http_errors": metrics.get("brapi.http_error", 0),
            "invalid_payloads": metrics.get("brapi.invalid_payload", 0),
        },
    }
