"""Email Dead-Letter Queue backed by Redis (issue #1049).

When ``ResendEmailProvider`` exhausts its tenacity retries, the message is
pushed here instead of being silently discarded.  The DLQ persists across
restarts (Redis list), supports manual/automated retry, and exposes a
Prometheus gauge so CloudWatch can alert when the queue grows.

Redis key
---------
``auraxis:email:dlq`` — a Redis LIST where each element is a JSON-encoded
``_DLQEntry`` dict.  RPUSH on enqueue, LRANGE + LREM on retry.

Usage
-----
    from app.services.email_dlq import get_email_dlq

    dlq = get_email_dlq()
    dlq.push(message, reason="Resend 503 after 3 retries")
    processed = dlq.retry_pending(limit=50)
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.email_provider import EmailMessage, EmailProvider

logger = logging.getLogger("auraxis.email_dlq")

_DLQ_KEY = "auraxis:email:dlq"
_MAX_STORED = 1_000  # hard cap — oldest entries trimmed when exceeded


@dataclass
class _DLQEntry:
    to_email: str
    subject: str
    html: str
    text: str
    tag: str
    reason: str
    enqueued_at: float  # unix timestamp


def _entry_from_message(message: "EmailMessage", *, reason: str) -> _DLQEntry:
    return _DLQEntry(
        to_email=message.to_email,
        subject=message.subject,
        html=message.html,
        text=message.text,
        tag=message.tag,
        reason=reason,
        enqueued_at=time.time(),
    )


def _message_from_entry(entry: _DLQEntry) -> "EmailMessage":
    from app.services.email_provider import EmailMessage

    return EmailMessage(
        to_email=entry.to_email,
        subject=entry.subject,
        html=entry.html,
        text=entry.text,
        tag=entry.tag,
    )


class _NoOpEmailDLQ:
    """Fallback DLQ used when Redis is unavailable — logs and discards."""

    def push(self, message: "EmailMessage", *, reason: str) -> None:
        logger.error(
            "email_dlq: Redis unavailable — email LOST to=%s subject=%r reason=%s",
            message.to_email,
            message.subject,
            reason,
        )

    def retry_pending(self, *, limit: int = 50) -> int:
        return 0

    def list_pending(self) -> list[dict[str, Any]]:
        return []

    def size(self) -> int:
        return 0

    @property
    def available(self) -> bool:
        return False


class RedisEmailDLQ:
    """Redis-backed email DLQ with retry support."""

    def __init__(self, client: Any) -> None:
        self._client = client

    def push(self, message: "EmailMessage", *, reason: str) -> None:
        entry = _entry_from_message(message, reason=reason)
        try:
            self._client.rpush(_DLQ_KEY, json.dumps(asdict(entry)))
            # Cap list length to avoid unbounded growth
            self._client.ltrim(_DLQ_KEY, -_MAX_STORED, -1)
            queue_size = self._client.llen(_DLQ_KEY)
            logger.warning(
                "email_dlq: pushed to=%s subject=%r reason=%s dlq_size=%d",
                message.to_email,
                message.subject,
                reason,
                queue_size,
            )
            _update_dlq_size_metric(queue_size)
        except Exception:
            logger.exception(
                "email_dlq: failed to push to Redis — email LOST to=%s",
                message.to_email,
            )

    def retry_pending(self, *, limit: int = 50) -> int:
        """Re-attempt delivery for up to *limit* pending messages.

        Each successfully delivered message is removed from the DLQ.
        Failed re-attempts are re-enqueued with an updated ``reason``.
        Returns the count of successfully delivered messages.
        """
        from app.services.email_provider import (
            EmailProviderError,
            get_default_email_provider,
        )

        try:
            raw_entries = self._client.lrange(_DLQ_KEY, 0, limit - 1)
        except Exception:
            logger.exception("email_dlq: failed to read from Redis")
            return 0

        if not raw_entries:
            return 0

        provider: EmailProvider = get_default_email_provider()
        delivered = 0

        for raw in raw_entries:
            try:
                data = json.loads(
                    raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                )
                entry = _DLQEntry(**data)
            except Exception:
                logger.exception("email_dlq: could not deserialise entry — skipping")
                self._client.lrem(_DLQ_KEY, 1, raw)
                continue

            message = _message_from_entry(entry)
            try:
                provider.send(message)
                self._client.lrem(_DLQ_KEY, 1, raw)
                delivered += 1
                logger.info(
                    "email_dlq: retry ok to=%s subject=%r",
                    entry.to_email,
                    entry.subject,
                )
            except EmailProviderError as exc:
                logger.warning(
                    "email_dlq: retry failed to=%s reason=%s — keeping in queue",
                    entry.to_email,
                    str(exc),
                )
                # Update reason and re-queue at end
                self._client.lrem(_DLQ_KEY, 1, raw)
                entry.reason = f"retry_failed: {exc}"
                self._client.rpush(_DLQ_KEY, json.dumps(asdict(entry)))

        queue_size = self._client.llen(_DLQ_KEY)
        _update_dlq_size_metric(queue_size)
        logger.info(
            "email_dlq: retry run complete delivered=%d remaining=%d",
            delivered,
            queue_size,
        )
        return delivered

    def list_pending(self) -> list[dict[str, Any]]:
        try:
            raw_entries = self._client.lrange(_DLQ_KEY, 0, 99)
        except Exception:
            logger.exception("email_dlq: failed to list entries")
            return []
        result = []
        for raw in raw_entries:
            try:
                data = json.loads(
                    raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                )
                # Redact html/text from listing output — can be large
                data.pop("html", None)
                data.pop("text", None)
                result.append(data)
            except Exception:
                continue
        return result

    def size(self) -> int:
        try:
            return int(self._client.llen(_DLQ_KEY))
        except Exception:
            return 0

    @property
    def available(self) -> bool:
        return True


# ── Prometheus metric ─────────────────────────────────────────────────────────

_DLQ_SIZE_GAUGE: Any = None


def _get_dlq_size_gauge() -> Any:
    global _DLQ_SIZE_GAUGE  # noqa: PLW0603
    if _DLQ_SIZE_GAUGE is not None:
        return _DLQ_SIZE_GAUGE
    try:
        from prometheus_client import Gauge

        _DLQ_SIZE_GAUGE = Gauge(
            "auraxis_email_dlq_size",
            "Number of emails pending in the dead-letter queue",
        )
    except Exception:
        pass
    return _DLQ_SIZE_GAUGE


def _update_dlq_size_metric(size: int) -> None:
    gauge = _get_dlq_size_gauge()
    if gauge is not None:
        try:
            gauge.set(size)
        except Exception:
            pass


# ── Singleton factory ─────────────────────────────────────────────────────────

_dlq_instance: RedisEmailDLQ | _NoOpEmailDLQ | None = None


def get_email_dlq() -> RedisEmailDLQ | _NoOpEmailDLQ:
    """Return the module-level DLQ singleton (built lazily)."""
    global _dlq_instance  # noqa: PLW0603
    if _dlq_instance is None:
        _dlq_instance = _build_dlq()
    return _dlq_instance


def reset_email_dlq_for_tests() -> None:
    """Reset singleton so tests can inject a fresh instance."""
    global _dlq_instance  # noqa: PLW0603
    _dlq_instance = None


def _build_dlq() -> RedisEmailDLQ | _NoOpEmailDLQ:
    import importlib
    import os

    redis_url = str(os.getenv("REDIS_URL", "")).strip()
    if not redis_url:
        logger.info("email_dlq: REDIS_URL not set — using no-op DLQ")
        return _NoOpEmailDLQ()

    try:
        redis_cls = importlib.import_module("redis").Redis
    except Exception:
        logger.warning("email_dlq: redis package unavailable — using no-op DLQ")
        return _NoOpEmailDLQ()

    try:
        client = redis_cls.from_url(redis_url, decode_responses=False)
        client.ping()
        logger.info("email_dlq: Redis connected")
        return RedisEmailDLQ(client)
    except Exception:
        logger.warning(
            "email_dlq: Redis connection failed — using no-op DLQ", exc_info=True
        )
        return _NoOpEmailDLQ()


__all__ = [
    "RedisEmailDLQ",
    "get_email_dlq",
    "reset_email_dlq_for_tests",
]
