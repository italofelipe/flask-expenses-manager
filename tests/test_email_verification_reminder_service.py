"""Tests for email_verification_reminder_service.

Covers:
- Happy path D-7 dispatch for unverified user created 7 days into grace
- Happy path D-1 dispatch for unverified user created 13 days into grace
- Idempotency: running twice on the same day does not duplicate emails
- Skip already-verified users
- Skip soft-deleted users
- Skip when creation_date doesn't match the target window
- Invalid window raises ValueError
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

import pytest

from app.application.services.email_verification_reminder_service import (
    EmailVerificationReminderResult,
    dispatch_email_verification_reminders,
)
from app.extensions.database import db
from app.models.user import User
from app.services.email_provider import get_email_outbox

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(
    *,
    app,
    created_at: datetime,
    email_verified_at: datetime | None = None,
    deleted_at: datetime | None = None,
    email_suffix: str = "",
) -> User:
    suffix = email_suffix or uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        name=f"Test {suffix}",
        email=f"verify-{suffix}@test.com",
        password="hash",
        created_at=created_at,
        email_verified_at=email_verified_at,
        deleted_at=deleted_at,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _drain_outbox() -> None:
    """Clear the in-memory outbox between assertions."""
    outbox = get_email_outbox()
    outbox.clear()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_dispatches_d7_reminder_for_unverified_user_at_grace_minus_7(app) -> None:
    today = date(2030, 6, 15)
    # grace is 14d, so user created 7 days ago lands in the D-7 window
    with app.app_context():
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=7), datetime.min.time())
            + timedelta(hours=10),
        )
        result = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )

        assert isinstance(result, EmailVerificationReminderResult)
        assert result.scanned == 1
        assert result.sent == 1
        outbox = get_email_outbox()
        assert len(outbox) == 1
        assert outbox[0]["tag"] == "email_verification_reminder_7d"
        _drain_outbox()


def test_dispatches_d1_reminder_for_unverified_user_at_grace_minus_1(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=13), datetime.min.time())
            + timedelta(hours=10),
        )
        result = dispatch_email_verification_reminders(
            days_until_deadline=1, today=today
        )

        assert result.scanned == 1
        assert result.sent == 1
        outbox = get_email_outbox()
        assert outbox[0]["tag"] == "email_verification_reminder_1d"
        _drain_outbox()


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_is_idempotent_per_day(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=7), datetime.min.time())
            + timedelta(hours=10),
        )
        first = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )
        second = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )

        assert first.sent == 1
        assert second.sent == 0
        assert second.skipped == 1
        # outbox holds only the first dispatch
        outbox = get_email_outbox()
        assert len(outbox) == 1
        _drain_outbox()


# ---------------------------------------------------------------------------
# Skip cases
# ---------------------------------------------------------------------------


def test_skips_verified_user(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=7), datetime.min.time())
            + timedelta(hours=10),
            email_verified_at=datetime.combine(
                today - timedelta(days=6), datetime.min.time()
            ),
        )
        result = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )

        assert result.scanned == 0
        assert result.sent == 0


def test_skips_soft_deleted_user(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=7), datetime.min.time())
            + timedelta(hours=10),
            deleted_at=datetime.combine(today - timedelta(days=2), datetime.min.time()),
        )
        result = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )

        assert result.scanned == 0
        assert result.sent == 0


def test_skips_user_outside_target_creation_window(app) -> None:
    today = date(2030, 6, 15)
    with app.app_context():
        # Created 5 days ago — not in D-7 window (would need exactly 7)
        _make_user(
            app=app,
            created_at=datetime.combine(today - timedelta(days=5), datetime.min.time())
            + timedelta(hours=10),
        )
        result = dispatch_email_verification_reminders(
            days_until_deadline=7, today=today
        )

        assert result.scanned == 0


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_invalid_window_raises_value_error(app) -> None:
    with app.app_context():
        with pytest.raises(ValueError):
            dispatch_email_verification_reminders(days_until_deadline=42)
