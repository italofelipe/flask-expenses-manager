"""Email provider adapter for transactional email delivery."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol, cast, runtime_checkable

import requests
from requests import Response
from requests.exceptions import RequestException

from app.http.runtime import (
    runtime_debug_or_testing,
    runtime_extension,
    set_runtime_extension,
)
from app.services.retry_wrapper import with_retry

_DEFAULT_RESEND_BASE_URL = "https://api.resend.com"
_REQUEST_TIMEOUT_SECONDS = 15.0
_RESEND_PROVIDER = "resend"
_STUB_PROVIDER = "stub"


class EmailProviderError(RuntimeError):
    """Raised when an email provider fails in a recoverable way."""


@dataclass(frozen=True)
class EmailMessage:
    to_email: str
    subject: str
    html: str
    text: str
    tag: str


@dataclass(frozen=True)
class EmailDeliveryResult:
    provider: str
    provider_message_id: str | None = None


@runtime_checkable
class EmailProvider(Protocol):
    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        """Deliver a transactional email."""
        ...


def _env(name: str, default: str = "") -> str:
    return str(os.getenv(name, default)).strip()


def get_email_outbox() -> list[dict[str, str]]:
    outbox = runtime_extension("email_outbox")
    if isinstance(outbox, list):
        return cast(list[dict[str, str]], outbox)
    set_runtime_extension("email_outbox", [])
    return cast(list[dict[str, str]], runtime_extension("email_outbox", []))


class StubEmailProvider:
    """Safe transactional email provider for tests and local development."""

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        get_email_outbox().append(
            {
                "provider": _STUB_PROVIDER,
                "email": message.to_email,
                "subject": message.subject,
                "html": message.html,
                "text": message.text,
                "tag": message.tag,
            }
        )
        return EmailDeliveryResult(provider=_STUB_PROVIDER)


def _raise_for_error_response(response: Response) -> None:
    if response.ok:
        return
    try:
        payload = cast(dict[str, Any], response.json())
    except ValueError:
        payload = {}
    message = str(
        payload.get("message") or payload.get("name") or response.text
    ).strip()
    error_message = message or "unknown error"
    raise EmailProviderError(
        f"Resend request failed with status {response.status_code}: {error_message}"
    )


class ResendEmailProvider:
    """Transactional email provider backed by Resend."""

    def __init__(self) -> None:
        self._api_key = _env("RESEND_API_KEY")
        self._base_url = _env("RESEND_BASE_URL", _DEFAULT_RESEND_BASE_URL)
        self._from_email = _env("EMAIL_FROM")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "accept": "application/json",
                "content-type": "application/json",
                "authorization": f"Bearer {self._api_key}",
            }
        )

    def _ensure_enabled(self) -> None:
        if not self._api_key:
            raise EmailProviderError(
                "RESEND_API_KEY is required when EMAIL_PROVIDER=resend"
            )
        if not self._from_email:
            raise EmailProviderError(
                "EMAIL_FROM is required when EMAIL_PROVIDER=resend"
            )

    def send(self, message: EmailMessage) -> EmailDeliveryResult:
        self._ensure_enabled()
        payload = {
            "from": self._from_email,
            "to": [message.to_email],
            "subject": message.subject,
            "html": message.html,
            "text": message.text,
            "tags": [{"name": "kind", "value": message.tag}],
        }

        @with_retry(provider="resend")
        def _post() -> EmailDeliveryResult:
            # Let RequestException propagate so tenacity can retry on
            # transient failures (Timeout, ConnectionError, HTTPError).
            # After retries are exhausted, the exception is caught below
            # and re-raised as EmailProviderError.
            response = self._session.post(
                f"{self._base_url.rstrip('/')}/emails",
                json=payload,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
            _raise_for_error_response(response)
            body = cast(dict[str, object], response.json())
            return EmailDeliveryResult(
                provider=_RESEND_PROVIDER,
                provider_message_id=str(body.get("id") or "").strip() or None,
            )

        try:
            return _post()
        except RequestException as exc:
            raise EmailProviderError("Resend request failed") from exc

    def send_with_dlq_fallback(self, message: EmailMessage) -> EmailDeliveryResult:
        """Send email; push to DLQ if all retries are exhausted."""
        from app.services.email_dlq import get_email_dlq

        try:
            return self.send(message)
        except EmailProviderError as exc:
            get_email_dlq().push(message, reason=str(exc))
            raise


def get_default_email_provider() -> EmailProvider:
    provider_name = _env("EMAIL_PROVIDER").lower()
    if provider_name == _RESEND_PROVIDER and not runtime_debug_or_testing():
        return ResendEmailProvider()
    if provider_name == _RESEND_PROVIDER:
        return ResendEmailProvider()
    return StubEmailProvider()


__all__ = [
    "EmailDeliveryResult",
    "EmailMessage",
    "EmailProvider",
    "EmailProviderError",
    "ResendEmailProvider",
    "StubEmailProvider",
    "get_default_email_provider",
    "get_email_outbox",
]
