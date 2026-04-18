"""OutboundQueue — async job queue port for transactional emails (ARC-API-02).

The ``OutboundQueue`` Protocol is the *port* that separates email-dispatch
business logic from the transport mechanism.  Two adapters are provided:

``RQOutboundQueue``   — enqueues jobs into a Redis Queue.  Workers consume
    them asynchronously via ``flask worker run``.

``SyncOutboundQueue`` — executes jobs synchronously in the request thread.
    Used automatically when ``REDIS_URL`` is unset or Redis is unreachable,
    which covers all test and development environments without Redis.

The singleton factory ``get_default_outbound_queue()`` selects the right
adapter at startup and caches it for the process lifetime.
"""

from __future__ import annotations

import logging
import os
from typing import Protocol, runtime_checkable

logger = logging.getLogger("auraxis.outbound_queue")

_QUEUE_NAME = "auraxis_outbound"
_JOB_TIMEOUT = "5m"


@runtime_checkable
class OutboundQueue(Protocol):
    """Port for asynchronous outbound operations."""

    def enqueue_send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html: str,
        text: str,
        tag: str,
    ) -> str | None:
        """Enqueue an email send job.  Returns the job ID or ``None`` (sync path)."""
        ...


class SyncOutboundQueue:
    """Fallback adapter: executes send_email synchronously in the request thread.

    Used when Redis is unavailable or in test environments.  Failed sends are
    forwarded to the email DLQ exactly as the async job would do.
    """

    def enqueue_send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html: str,
        text: str,
        tag: str,
    ) -> None:
        from app.services.email_dlq import get_email_dlq
        from app.services.email_provider import EmailMessage, get_default_email_provider

        provider = get_default_email_provider()
        message = EmailMessage(
            to_email=to_email,
            subject=subject,
            html=html,
            text=text,
            tag=tag,
        )
        try:
            provider.send(message)
        except Exception as exc:
            logger.warning(
                "outbound_queue(sync): delivery failed tag=%s to=%s — pushing to DLQ",
                tag,
                to_email,
            )
            get_email_dlq().push(message, reason=str(exc))


class RQOutboundQueue:
    """Redis Queue adapter — enqueues jobs for worker consumption."""

    def __init__(self, redis_url: str) -> None:
        import redis as redis_lib
        import rq

        self._conn = redis_lib.Redis.from_url(redis_url, decode_responses=False)
        self._queue = rq.Queue(_QUEUE_NAME, connection=self._conn)

    def enqueue_send_email(
        self,
        *,
        to_email: str,
        subject: str,
        html: str,
        text: str,
        tag: str,
    ) -> str | None:
        try:
            job = self._queue.enqueue(
                "app.jobs.email_jobs.send_email",
                job_timeout=_JOB_TIMEOUT,
                to_email=to_email,
                subject=subject,
                html=html,
                text=text,
                tag=tag,
            )
            logger.debug(
                "outbound_queue(rq): enqueued tag=%s to=%s job_id=%s",
                tag,
                to_email,
                job.id,
            )
            return str(job.id)
        except Exception as exc:
            logger.warning(
                "outbound_queue(rq): enqueue failed — falling back to sync. reason=%s",
                str(exc),
            )
            _sync_fallback = SyncOutboundQueue()
            _sync_fallback.enqueue_send_email(
                to_email=to_email,
                subject=subject,
                html=html,
                text=text,
                tag=tag,
            )
            return None


# ── Singleton factory ─────────────────────────────────────────────────────────

_queue_instance: OutboundQueue | None = None


def get_default_outbound_queue() -> OutboundQueue:
    """Return the process-level outbound queue (lazy singleton)."""
    global _queue_instance  # noqa: PLW0603
    if _queue_instance is None:
        _queue_instance = _build_queue()
    return _queue_instance


def reset_outbound_queue_for_tests() -> None:
    """Reset the singleton so tests can inject a custom queue."""
    global _queue_instance  # noqa: PLW0603
    _queue_instance = None


def _build_queue() -> OutboundQueue:
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        logger.info("outbound_queue: REDIS_URL not set — using sync fallback")
        return SyncOutboundQueue()

    try:
        queue = RQOutboundQueue(redis_url)
        queue._conn.ping()
        logger.info("outbound_queue: Redis connected — using RQ adapter")
        return queue
    except Exception:
        logger.warning(
            "outbound_queue: Redis connection failed — using sync fallback",
            exc_info=True,
        )
        return SyncOutboundQueue()


__all__ = [
    "OutboundQueue",
    "RQOutboundQueue",
    "SyncOutboundQueue",
    "get_default_outbound_queue",
    "reset_outbound_queue_for_tests",
]
