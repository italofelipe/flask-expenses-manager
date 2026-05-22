# mypy: disable-error-code="import-untyped"
"""Sentry SDK initialisation for auraxis-api.

Call ``init_sentry()`` once at application startup (inside ``create_app()``).
The integration is a no-op when ``SENTRY_DSN`` is absent or empty, so local
development and test runs are never affected.

Required env vars:
    SENTRY_DSN           — project DSN from Sentry (absent = disabled)

Optional env vars:
    SENTRY_ENVIRONMENT   — "production" | "staging" | "dev"  (default: "dev")
    SENTRY_RELEASE       — release identifier, e.g. git sha or semver tag
    SENTRY_TRACES_RATE   — float 0-1 for performance tracing (default: 0.0)
    SENTRY_PROFILES_RATE — float 0-1 for profiling          (default: 0.0)
    SENTRY_ERROR_RATE    — float 0-1 for error sampling      (default: 1.0)

Quota protection:
    before_send drops HTTP 4xx exceptions (client errors) — they are expected
    and the primary cause of free-tier quota exhaustion. Only 5xx server errors
    and unhandled exceptions are forwarded to Sentry.
    SENTRY_ERROR_RATE provides an additional sampling knob (e.g. 0.5 = 50%).

Privacy:
    send_default_pii is ALWAYS false (LGPD compliance — see ADR #407).
"""

from __future__ import annotations

import os
import secrets
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sentry_sdk.types import Event, Hint


def _resolve_traces_rate(environment: str) -> float:
    """Resolve the active ``traces_sample_rate``.

    Honors an explicit ``SENTRY_TRACES_RATE`` env override; otherwise picks an
    env-aware default that matches the web/app side defaults (see PRs
    auraxis-web #928 and auraxis-app #451):

    - ``dev``                 → 1.0 (capture every trace for local debugging)
    - ``staging`` / ``preview`` → 0.5
    - everything else         → 0.0 (baseline production rate)

    Use a separate Sentry project for dev to keep prod quota clean.
    """
    explicit = os.getenv("SENTRY_TRACES_RATE")
    if explicit is not None and explicit.strip() != "":
        return float(explicit)
    if environment == "dev":
        return 1.0
    if environment in ("staging", "preview"):
        return 0.5
    return 0.0


def _before_send(event: Event, hint: Hint) -> Event | None:
    """Drop client errors (4xx) and apply error sampling to reduce quota use."""
    exc_info = hint.get("exc_info")
    if exc_info:
        _, exc_value, _ = exc_info
        # Drop werkzeug/Flask HTTP exceptions with status < 500 (client errors)
        status_code = getattr(exc_value, "code", None)
        if status_code is not None and status_code < 500:
            return None

    error_rate = float(os.getenv("SENTRY_ERROR_RATE", "1.0"))
    if error_rate < 1.0 and secrets.randbelow(1_000_000) >= round(
        error_rate * 1_000_000
    ):
        return None

    return event


def init_sentry() -> None:
    """Initialise the Sentry SDK.

    Safe to call multiple times (subsequent calls are no-ops if already
    initialised by the SDK's own guard).
    """
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        return

    try:
        import sentry_sdk
        from sentry_sdk.integrations.flask import FlaskIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    except ImportError:
        # sentry-sdk not installed — skip silently (should never happen in prod)
        print("[sentry] WARN: sentry-sdk not installed; Sentry disabled.")
        return

    environment = os.getenv("SENTRY_ENVIRONMENT", "dev")
    release = os.getenv("SENTRY_RELEASE", "")
    traces_sample_rate = _resolve_traces_rate(environment)
    profiles_sample_rate = float(os.getenv("SENTRY_PROFILES_RATE", "0.0"))

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            FlaskIntegration(),
            SqlalchemyIntegration(),
        ],
        environment=environment,
        release=release or None,
        traces_sample_rate=traces_sample_rate,
        profiles_sample_rate=profiles_sample_rate,
        before_send=_before_send,
        # LGPD — never attach user IPs, cookies, or request bodies by default.
        send_default_pii=False,
    )
