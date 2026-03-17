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

Privacy:
    send_default_pii is ALWAYS false (LGPD compliance — see ADR #407).
"""

from __future__ import annotations

import os


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
    traces_sample_rate = float(os.getenv("SENTRY_TRACES_RATE", "0.0"))
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
        # LGPD — never attach user IPs, cookies, or request bodies by default.
        send_default_pii=False,
    )
