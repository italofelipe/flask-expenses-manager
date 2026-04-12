"""retry_wrapper.py — PERF-GAP-04: shared retry + exponential backoff decorator.

Wraps external HTTP calls (Resend, Asaas, BRAPI) with tenacity-based retry so
that transient 5xx / network errors are retried up to 3 times before surfacing
to the caller, while Sentry and the structured logger record each attempt.

Usage
-----
    from app.services.retry_wrapper import with_retry

    @with_retry(provider="resend")
    def _send_email() -> ...:
        ...

Or as a one-shot helper around an existing callable:

    result = with_retry(provider="brapi")(my_fn)(arg1, kwarg=v)
"""

from __future__ import annotations

import logging
from typing import Any, Callable, TypeVar

import sentry_sdk
from requests.exceptions import ConnectionError, HTTPError, Timeout
from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

_logger = logging.getLogger("auraxis.retry")

_RETRYABLE = (HTTPError, Timeout, ConnectionError)

F = TypeVar("F", bound=Callable[..., Any])

_MAX_ATTEMPTS = 3
_WAIT_INITIAL = 2
_WAIT_MAX = 10
_JITTER_MAX = 1  # up to 1 s random jitter to avoid thundering herd


def _make_before_sleep(provider: str) -> Callable[[RetryCallState], None]:
    def _before_sleep(retry_state: RetryCallState) -> None:
        attempt = retry_state.attempt_number
        outcome = retry_state.outcome
        exc = outcome.exception() if outcome else None
        elapsed = retry_state.seconds_since_start
        next_wait: float | None
        if retry_state.next_action is not None:
            next_wait = getattr(retry_state.next_action, "sleep", None)
        else:
            next_wait = None
        _logger.warning(
            "retry provider=%s attempt=%d elapsed=%.2fs outcome=%s "
            "exception=%r next_wait=%.1fs",
            provider,
            attempt,
            elapsed,
            "failure",
            exc,
            next_wait or 0.0,
        )
        sentry_sdk.add_breadcrumb(
            category="retry",
            message=f"{provider} transient failure — retrying (attempt {attempt})",
            level="warning",
            data={
                "provider": provider,
                "attempt": attempt,
                "elapsed": elapsed,
                "outcome": "failure",
                "exception": repr(exc),
                "next_wait": next_wait,
            },
        )

    return _before_sleep


def with_retry(*, provider: str) -> Callable[[F], F]:
    """Return a tenacity retry decorator configured for the given provider.

    Retries up to 3 times on ``HTTPError``, ``Timeout``, or
    ``ConnectionError`` with exponential backoff + random jitter
    (2 s base → 4 s → 10 s cap, ±1 s jitter to avoid thundering herd).
    Each retry emits a structured log line and a Sentry breadcrumb.
    """
    decorator: Callable[[F], F] = retry(
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential_jitter(
            initial=_WAIT_INITIAL,
            max=_WAIT_MAX,
            jitter=_JITTER_MAX,
        ),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=_make_before_sleep(provider),
        reraise=True,
    )
    return decorator
