"""Email verification reminders — D-7 and D-1 dispatch service.

Mirrors the pattern of ``transaction_reminder_service`` but for the
14-day email verification grace period introduced in #1325 / PR #1326.

The reminder targets users whose grace-period deadline falls in
``days_until_deadline`` days from ``today``:

    target_creation_day = today - (grace_days - days_until_deadline)

Idempotency uses the ``Alert`` table with ``entity_type='user'`` and
``entity_id=user.id`` so we can safely run the job multiple times per day
without duplicating emails.

Unlike transaction reminders, this dispatch does **not** require the
``email_reminders`` entitlement — verification is system-critical and
every unverified user must receive it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Sequence, cast
from uuid import UUID

from flask import current_app

from app.extensions.database import db
from app.models.alert import Alert, AlertStatus
from app.models.user import User
from app.services.email_dlq import get_email_dlq
from app.services.email_provider import (
    EmailMessage,
    EmailProviderError,
    get_default_email_provider,
)
from app.services.email_templates.base import render_email_verification_reminder_email
from app.utils.datetime_utils import utc_now_naive

_REMINDER_WINDOWS = {
    7: "email_verification_reminder_7d",
    1: "email_verification_reminder_1d",
}

_USER_ENTITY_TYPE = "user"


@dataclass(frozen=True)
class EmailVerificationReminderResult:
    scanned: int
    sent: int
    skipped: int
    queued: int = 0


def _start_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.min.time())


def _end_of_day(day: date) -> datetime:
    return datetime.combine(day, datetime.max.time())


def _existing_alert(*, user_id: UUID, category: str, day: date) -> Alert | None:
    return cast(
        Alert | None,
        Alert.query.filter(
            Alert.user_id == user_id,
            Alert.category == category,
            Alert.entity_type == _USER_ENTITY_TYPE,
            Alert.entity_id == user_id,
            Alert.triggered_at >= _start_of_day(day),
            Alert.triggered_at <= _end_of_day(day),
        ).first(),
    )


def _eligible_users(*, target_creation_day: date) -> Sequence[User]:
    return cast(
        Sequence[User],
        User.query.filter(
            User.email_verified_at.is_(None),
            User.created_at >= _start_of_day(target_creation_day),
            User.created_at <= _end_of_day(target_creation_day),
            User.deleted_at.is_(None),
        ).all(),
    )


def _build_subject(*, days_until_deadline: int) -> str:
    if days_until_deadline == 1:
        return "Último dia para confirmar seu email — Auraxis"
    return f"Faltam {days_until_deadline} dias para confirmar seu email — Auraxis"


def _send_or_queue(message: EmailMessage) -> AlertStatus:
    try:
        get_default_email_provider().send(message)
        return AlertStatus.SENT
    except EmailProviderError as exc:
        get_email_dlq().push(message, reason=str(exc))
        return AlertStatus.PENDING


def dispatch_email_verification_reminders(
    *, days_until_deadline: int, today: date | None = None
) -> EmailVerificationReminderResult:
    """Send verification reminders to users at the requested countdown window.

    Args:
        days_until_deadline: 7 (D-7) or 1 (D-1).
        today: Override the reference day for tests.

    Returns:
        EmailVerificationReminderResult with scan/send/skip/queue counters.
    """
    category = _REMINDER_WINDOWS.get(days_until_deadline)
    if category is None:
        raise ValueError("Unsupported reminder window")

    grace_days = int(current_app.config.get("EMAIL_VERIFICATION_GRACE_PERIOD_DAYS", 14))
    reference_day = today or date.today()
    target_creation_day = reference_day - timedelta(
        days=grace_days - days_until_deadline
    )

    scanned = 0
    sent = 0
    skipped = 0
    queued = 0

    for user in _eligible_users(target_creation_day=target_creation_day):
        scanned += 1
        if _existing_alert(user_id=user.id, category=category, day=reference_day):
            skipped += 1
            continue

        email_html, email_text = render_email_verification_reminder_email(
            days_until_deadline=days_until_deadline,
        )
        message = EmailMessage(
            to_email=str(user.email),
            subject=_build_subject(days_until_deadline=days_until_deadline),
            html=email_html,
            text=email_text,
            tag=category,
        )
        alert_status = _send_or_queue(message)
        if alert_status == AlertStatus.SENT:
            sent += 1
            sent_at = utc_now_naive()
        else:
            queued += 1
            sent_at = None

        db.session.add(
            Alert(
                user_id=user.id,
                category=category,
                status=alert_status,
                entity_type=_USER_ENTITY_TYPE,
                entity_id=user.id,
                triggered_at=_start_of_day(reference_day),
                sent_at=sent_at,
            )
        )

    db.session.commit()
    return EmailVerificationReminderResult(
        scanned=scanned, sent=sent, skipped=skipped, queued=queued
    )


__all__ = [
    "EmailVerificationReminderResult",
    "dispatch_email_verification_reminders",
]
