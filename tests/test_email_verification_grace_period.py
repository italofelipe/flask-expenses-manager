"""Tests for the 14-day email verification grace period + soft-block decorator.

Coverage:
- User.email_verified hybrid property (verified vs unverified)
- User.email_verification_deadline_at (computed from created_at + grace_days)
- User.email_verification_required_now (False within grace, True after)
- User.days_until_email_required (countdown)
- @require_email_verified decorator behavior:
  - allows verified users
  - allows users within grace period
  - blocks users past grace period (403 EMAIL_VERIFICATION_REQUIRED)
  - no-op when EMAIL_VERIFICATION_ENFORCE=false
- /user/me exposes email_verification block in canonical payload
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.extensions.database import db
from app.models.user import User

# ---------------------------------------------------------------------------
# Hybrid property tests
# ---------------------------------------------------------------------------


def _make_user(
    *,
    app,
    created_at: datetime | None = None,
    email_verified_at: datetime | None = None,
) -> User:
    """Persist a User with controlled timestamps for grace-period testing."""
    suffix = uuid.uuid4().hex[:8]
    with app.app_context():
        user = User(
            name=f"Test {suffix}",
            email=f"grace-{suffix}@test.com",
            password="hashed-not-real",
            created_at=created_at or datetime.now(UTC).replace(tzinfo=None),
            email_verified_at=email_verified_at,
        )
        db.session.add(user)
        db.session.commit()
        db.session.refresh(user)
        return user


def test_email_verified_true_when_email_verified_at_is_set(app):
    user = _make_user(app=app, email_verified_at=datetime.now(UTC).replace(tzinfo=None))
    with app.app_context():
        assert user.email_verified is True
        assert user.email_verification_required_now is False
        assert user.email_verification_deadline_at is None
        assert user.days_until_email_required is None


def test_email_verified_false_when_unconfirmed(app):
    user = _make_user(app=app)
    with app.app_context():
        assert user.email_verified is False


def test_deadline_within_grace_period_does_not_require_verification(app):
    # Created 1 hour ago — well within 14-day grace period
    recent = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=1)
    user = _make_user(app=app, created_at=recent)
    with app.app_context():
        assert user.email_verification_required_now is False
        assert user.email_verification_deadline_at is not None
        # Deadline should be ~14 days from created_at
        days_remaining = (
            user.email_verification_deadline_at - datetime.now(UTC).replace(tzinfo=None)
        ).days
        assert days_remaining >= 13


def test_deadline_past_grace_period_requires_verification(app):
    # Created 15 days ago — past 14-day grace
    old = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=15)
    user = _make_user(app=app, created_at=old)
    with app.app_context():
        assert user.email_verification_required_now is True
        assert user.days_until_email_required is not None
        assert user.days_until_email_required < 0


def test_days_until_email_required_counts_down(app):
    # Created 10 days ago — should have ~4 days remaining
    created = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=10)
    user = _make_user(app=app, created_at=created)
    with app.app_context():
        days = user.days_until_email_required
        assert days is not None
        assert 3 <= days <= 4


# ---------------------------------------------------------------------------
# Decorator integration tests (via existing endpoint)
# ---------------------------------------------------------------------------


def _register_and_login(client) -> tuple[str, str, str]:
    """Register a fresh user, return (email, jwt_token, user_id)."""
    suffix = uuid.uuid4().hex[:8]
    email = f"gate-{suffix}@test.com"
    password = "StrongPass@123"
    reg_resp = client.post(
        "/auth/register",
        json={"name": f"Gate User {suffix}", "email": email, "password": password},
    )
    assert reg_resp.status_code == 201, f"Register failed: {reg_resp.get_json()}"
    user_id = reg_resp.get_json().get("data", {}).get("user", {}).get(
        "id"
    ) or reg_resp.get_json().get("user_id")
    resp = client.post("/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    body = resp.get_json()
    token = body.get("token") or body.get("data", {}).get("token")
    return email, token, user_id


def _force_user_created_at(app, email: str, *, days_ago: int) -> None:
    """Force user.created_at to N days in the past for grace-period testing."""
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        user.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            days=days_ago
        )
        db.session.commit()


def test_create_transaction_blocked_for_unverified_user_past_grace(app, client):
    email, token, _ = _register_and_login(client)
    _force_user_created_at(app, email, days_ago=15)

    resp = client.post(
        "/transactions",
        json={
            "name": "Test",
            "amount": 100.0,
            "type": "expense",
            "category": "outros",
            "due_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    body = resp.get_json()
    assert body.get("error") == "EMAIL_VERIFICATION_REQUIRED"
    assert body.get("resend_endpoint") == "/auth/email/resend"


def test_create_transaction_allowed_within_grace_period(app, client):
    email, token, _ = _register_and_login(client)
    # Default created_at is now() — well within grace
    resp = client.post(
        "/transactions",
        json={
            "name": "Allowed",
            "amount": 50.0,
            "type": "expense",
            "category": "outros",
            "due_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should NOT be 403 (may be 201 or other status depending on validation)
    assert resp.status_code != 403


def test_decorator_is_noop_when_enforce_disabled(app, client, monkeypatch):
    monkeypatch.setattr(
        app.config,
        "get",
        lambda key, default=None: (
            False
            if key == "EMAIL_VERIFICATION_ENFORCE"
            else app.config[key]
            if key in app.config
            else default
        ),
    )
    email, token, _ = _register_and_login(client)
    _force_user_created_at(app, email, days_ago=20)

    resp = client.post(
        "/transactions",
        json={
            "name": "Test",
            "amount": 100.0,
            "type": "expense",
            "category": "outros",
            "due_date": "2026-12-31",
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    # When ENFORCE=false, should not block on email verification
    assert (
        resp.status_code != 403
        or resp.get_json().get("error") != "EMAIL_VERIFICATION_REQUIRED"
    )


# ---------------------------------------------------------------------------
# /user/me exposure
# ---------------------------------------------------------------------------


def test_user_me_exposes_email_verification_block(app, client):
    email, token, _ = _register_and_login(client)
    resp = client.get(
        "/user/me",
        headers={
            "Authorization": f"Bearer {token}",
            "X-API-Contract": "v3",
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    user_payload = body.get("data", {}).get("user", {})
    email_block = user_payload.get("email_verification")
    assert email_block is not None
    assert "verified" in email_block
    assert "deadline_at" in email_block
    assert "required_now" in email_block
    assert "days_remaining" in email_block
    assert email_block["verified"] is False  # Fresh user, not yet confirmed
    assert email_block["required_now"] is False  # Within grace period
