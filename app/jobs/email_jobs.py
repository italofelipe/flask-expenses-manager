"""RQ job definitions for email delivery (ARC-API-02).

Each function in this module is an RQ *job* — a top-level importable callable
that the ``rq`` worker executes in a separate process.  When Redis is
unavailable the ``SyncOutboundQueue`` calls these functions synchronously so
the same logic path is exercised in all environments.

Failed deliveries are forwarded to the email DLQ (``app.services.email_dlq``)
so they can be retried via the existing ``flask email-dlq retry`` CLI.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("auraxis.jobs.email")


def send_email(
    *,
    to_email: str,
    subject: str,
    html: str,
    text: str,
    tag: str,
) -> dict[str, str]:
    """Send a single transactional email via the default provider.

    On ``EmailProviderError`` the message is pushed to the DLQ and the
    exception is re-raised so RQ marks the job as failed and applies its own
    retry/failure policy.
    """
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
        result = provider.send(message)
        logger.info(
            "email_job: sent tag=%s to=%s message_id=%s",
            tag,
            to_email,
            getattr(result, "provider_message_id", "n/a"),
        )
        return {"status": "sent", "to_email": to_email, "tag": tag}
    except Exception as exc:
        logger.warning(
            "email_job: delivery failed tag=%s to=%s reason=%s — pushing to DLQ",
            tag,
            to_email,
            str(exc),
        )
        get_email_dlq().push(message, reason=str(exc))
        raise
