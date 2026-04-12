"""
Refresh-token body-inclusion policy (SEC-1 dual-mode close-out).

SEC-GAP-01 introduced the httpOnly `auraxis_refresh` cookie while keeping
`refresh_token` in the JSON response body for backward compatibility with
legacy clients. This module decides — per request — whether the body should
still echo the refresh token, enabling a controlled migration:

- Global switch: `AURAXIS_REFRESH_COOKIE_ONLY=true` strips the token for every
  response (final cut-over).
- Per-request opt-in: clients that have already migrated may send the header
  `X-Refresh-Cookie-Only: 1` to ask the server to omit the token from the body
  even while the global switch is still off. Useful during the migration
  window to exercise the new code path without flipping the switch for all
  clients at once.

The helper is pure and imports no Flask globals; the caller passes the
current header map so it is trivial to unit-test.
"""

from __future__ import annotations

from flask import current_app

COOKIE_ONLY_HEADER = "X-Refresh-Cookie-Only"

_TRUTHY = frozenset({"1", "true", "yes", "on"})


def _header_is_truthy(value: str | None) -> bool:
    """
    Returns whether the header value opts in to cookie-only mode.

    Accepts the common truthy spellings ``1``, ``true``, ``yes``, ``on``
    (case-insensitive). Any other value — including an empty string — is
    treated as opt-out so ambiguous values never accidentally strip the body.
    """
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY


def should_omit_refresh_token_in_body(
    *,
    header_value: str | None,
    global_flag: bool | None = None,
) -> bool:
    """
    Decides whether to omit ``refresh_token`` from the JSON response body.

    Args:
        header_value: The value of ``X-Refresh-Cookie-Only`` on the current
            request, or ``None`` if the header is absent.
        global_flag: Override for the global config flag, for testing. When
            ``None`` the function reads ``AURAXIS_REFRESH_COOKIE_ONLY`` from
            ``current_app.config`` inside a Flask request context.

    Returns:
        ``True`` when the response body must not include ``refresh_token`` —
        either because the global flag is on or because the client opted in
        via the per-request header.
    """
    if global_flag is None:
        global_flag = bool(current_app.config.get("AURAXIS_REFRESH_COOKIE_ONLY", False))
    if global_flag:
        return True
    return _header_is_truthy(header_value)
