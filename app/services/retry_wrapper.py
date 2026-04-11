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
    wait_exponential,
)

_logger = logging.getLogger("auraxis.retry")

_RETRYABLE = (HTTPError, Timeout, ConnectionError)

F = TypeVar("F", bound=Callable[..., Any])

_MAX_ATTEMPTS = 3
_WAIT_MULTIPLIER = 1
_WAIT_MIN = 2
_WAIT_MAX = 10


def _make_before_sleep(provider: str) -> Callable[[RetryCallState], None]:
    def _before_sleep(retry_state: RetryCallState) -> None:
        attempt = retry_state.attempt_number
        exc = retry_state.outcome.exception() if retry_state.outcome else None
        next_wait: float | None
        if retry_state.next_action is not None:
            next_wait = getattr(retry_state.next_action, "sleep", None)
        else:
            next_wait = None
        _logger.warning(
            "retry provider=%s attempt=%d exception=%r next_wait=%.1fs",
            provider,
            attempt,
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
                "exception": repr(exc),
                "next_wait": next_wait,
            },
        )

    return _before_sleep


def with_retry(*, provider: str) -> Callable[[F], F]:
    """Return a tenacity retry decorator configured for the given provider.

    Retries up to 3 times on ``HTTPError``, ``Timeout``, or
    ``ConnectionError`` with exponential backoff (2 s → 4 s → 10 s cap).
    Each retry emits a structured log line and a Sentry breadcrumb.
    """
    decorator: Callable[[F], F] = retry(
        stop=stop_after_attempt(_MAX_ATTEMPTS),
        wait=wait_exponential(
            multiplier=_WAIT_MULTIPLIER,
            min=_WAIT_MIN,
            max=_WAIT_MAX,
        ),
        retry=retry_if_exception_type(_RETRYABLE),
        before_sleep=_make_before_sleep(provider),
        reraise=True,
    )
    return decorator
