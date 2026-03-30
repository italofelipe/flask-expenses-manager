"""Cloudflare Turnstile CAPTCHA verification service.

Verifies a client-side Turnstile token by calling the Cloudflare
siteverify endpoint.  The service is opt-in: when the secret key is
not configured (or the feature is explicitly disabled) every call
returns ``True`` so existing flows are never broken in dev/test.

Graceful-degradation rules
--------------------------
* Missing/empty token  → ``False``  (token required when CAPTCHA enabled)
* Cloudflare says invalid  → ``False``
* Network/timeout error  → ``True`` (fail-open) + warning log
* Feature disabled (no secret key or env flag off) → ``True``
"""

from __future__ import annotations

import logging
from typing import Any

import requests
from flask import current_app
from requests.exceptions import RequestException

logger = logging.getLogger(__name__)

_TURNSTILE_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v1/siteverify"
_REQUEST_TIMEOUT_SECONDS = 5


class CaptchaService:
    """Thin wrapper around the Cloudflare Turnstile siteverify API."""

    def __init__(self, secret_key: str, enabled: bool = True) -> None:
        self._secret_key = secret_key
        self._enabled = enabled

    def verify(self, token: str | None) -> bool:
        """Verify a Turnstile token obtained from the client.

        Returns ``True`` when the challenge passes or when CAPTCHA is
        disabled.  Returns ``False`` when the token is missing or
        explicitly rejected by Cloudflare.

        :param token: The ``cf-turnstile-response`` token sent by the browser.
        :returns: Whether the request should be allowed to proceed.
        """
        if not self._enabled or not self._secret_key:
            return True

        if not token:
            return False

        try:
            response = requests.post(
                _TURNSTILE_VERIFY_URL,
                data={"secret": self._secret_key, "response": token},
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            payload: dict[str, Any] = response.json()
            return bool(payload.get("success", False))
        except RequestException:
            current_app.logger.warning(
                "Turnstile verification request failed — failing open.",
                exc_info=True,
            )
            return True


def get_captcha_service() -> CaptchaService:
    """Resolve a ``CaptchaService`` instance from the current app config.

    :returns: Configured ``CaptchaService`` ready for use.
    """
    secret_key: str = (
        current_app.config.get("CLOUDFLARE_TURNSTILE_SECRET_KEY", "") or ""
    )
    enabled: bool = current_app.config.get("CLOUDFLARE_TURNSTILE_ENABLED", True)
    return CaptchaService(secret_key=secret_key, enabled=enabled)
