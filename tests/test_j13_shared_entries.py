"""Tests for J13 — shared entries, invitations and audit service."""

from __future__ import annotations

import uuid

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, suffix: str | None = None) -> tuple[str, str]:
    """Register a user and return (user_id, token)."""
    s = suffix or uuid.uuid4().hex[:8]
    email = f"j13-{s}@test.com"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"j13-{s}", "email": email, "password": password},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.get_json()
    token: str = login.get_json()["token"]
    profile = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    user_id: str = profile.get_json().get("id", "")
    return user_id, token


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _make_user(suffix: str | None = None):
    """Return a User instance with minimal required fields."""
    from app.models.user import User

    s = suffix or uuid.uuid4().hex[:6]
    return User(
        id=uuid.uuid4(),
        name=f"user-{s}",
        email=f"user-{s}@test.com",
        password="hashed",
    )


def _make_transaction(user_id: uuid.UUID):
    """Return a Transaction instance with minimal required fields."""
    from datetime import date

    from app.models.transaction import Transaction

    return Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        title="test txn",
        amount=100,
        type="EXPENSE",
        due_date=date(2026, 1, 1),
    )


# ---------------------------------------------------------------------------
# Shared entry service unit tests
# ---------------------------------------------------------------------------


def test_share_entry_appears_in_list_shared_by_me(app) -> None:
    """Creating a shared entry via service makes it visible in list_shared_by_me."""
    from app.extensions.database import db
    from app.services.shared_entry_service import list_shared_by_me, share_entry

    with app.app_context():
        owner = _make_user()
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="equal",
        )
        results = list_shared_by_me(owner_id=owner.id)
        assert any(str(r.id) == str(entry.id) for r in results)


def test_revoke_share_sets_status_revoked(app) -> None:
    """Revoking a shared entry sets its status to REVOKED."""
    from app.extensions.database import db
    from app.models.shared_entry import SharedEntryStatus
    from app.services.shared_entry_service import revoke_share, share_entry

    with app.app_context():
        owner = _make_user()
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="fixed",
        )
        revoked = revoke_share(shared_entry_id=entry.id, owner_id=owner.id)
        assert revoked.status == SharedEntryStatus.REVOKED


def test_revoke_share_non_owner_raises_forbidden(app) -> None:
    """Revoking a shared entry you don't own raises SharedEntryForbiddenError."""
    from app.extensions.database import db
    from app.services.shared_entry_service import (
        SharedEntryForbiddenError,
        revoke_share,
        share_entry,
    )

    with app.app_context():
        owner = _make_user("own")
        other = _make_user("oth")
        db.session.add_all([owner, other])
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="percentage",
        )
        with pytest.raises(SharedEntryForbiddenError):
            revoke_share(shared_entry_id=entry.id, owner_id=other.id)


# ---------------------------------------------------------------------------
# Invitation service unit tests
# ---------------------------------------------------------------------------


def test_accept_invitation_sets_status_accepted(app) -> None:
    """Accepting an invitation sets its status to ACCEPTED."""
    from app.extensions.database import db
    from app.models.shared_entry import InvitationStatus
    from app.services.invitation_service import accept_invitation, create_invitation
    from app.services.shared_entry_service import share_entry

    with app.app_context():
        owner = _make_user("inviter")
        invitee = _make_user("invitee")
        db.session.add_all([owner, invitee])
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="equal",
        )
        invitation = create_invitation(
            inviter_id=owner.id,
            shared_entry_id=entry.id,
            invitee_email=invitee.email,
        )
        accepted = accept_invitation(
            token=invitation.token, accepting_user_id=invitee.id
        )
        assert accepted.status == InvitationStatus.ACCEPTED
        assert accepted.to_user_id == invitee.id


def test_expired_token_raises_invitation_expired_error(app) -> None:
    """An already-expired invitation raises InvitationExpiredError on accept."""
    from datetime import timedelta

    from app.extensions.database import db
    from app.services.invitation_service import (
        InvitationExpiredError,
        accept_invitation,
        create_invitation,
    )
    from app.services.shared_entry_service import share_entry
    from app.utils.datetime_utils import utc_now_naive

    with app.app_context():
        owner = _make_user("exp")
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="equal",
        )
        invitation = create_invitation(
            inviter_id=owner.id,
            shared_entry_id=entry.id,
            invitee_email="expired@test.com",
            expires_in_hours=1,
        )
        # Manually back-date the expiry so it is already in the past
        invitation.expires_at = utc_now_naive() - timedelta(hours=2)
        db.session.commit()

        with pytest.raises(InvitationExpiredError):
            accept_invitation(token=invitation.token, accepting_user_id=uuid.uuid4())


def test_revoke_invitation_sets_status_revoked(app) -> None:
    """Revoking a pending invitation sets its status to REVOKED."""
    from app.extensions.database import db
    from app.models.shared_entry import InvitationStatus
    from app.services.invitation_service import create_invitation, revoke_invitation
    from app.services.shared_entry_service import share_entry

    with app.app_context():
        owner = _make_user("rvk")
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id,
            transaction_id=txn.id,
            split_type="equal",
        )
        inv = create_invitation(
            inviter_id=owner.id,
            shared_entry_id=entry.id,
            invitee_email="to-revoke@test.com",
        )
        revoked = revoke_invitation(invitation_id=inv.id, inviter_id=owner.id)
        assert revoked.status == InvitationStatus.REVOKED


# ---------------------------------------------------------------------------
# Audit service unit tests
# ---------------------------------------------------------------------------


def test_audit_log_records_events(app) -> None:
    """log_event creates a record and get_user_audit_log returns it."""
    from app.services.sharing_audit_service import get_user_audit_log, log_event

    with app.app_context():
        user_id = uuid.uuid4()
        resource_id = uuid.uuid4()
        event = log_event(
            user_id=user_id,
            action="share_entry.created",
            resource_type="shared_entry",
            resource_id=resource_id,
            metadata={"split_type": "equal"},
        )
        assert event.id is not None
        log = get_user_audit_log(user_id=user_id, limit=10)
        assert any(str(e.id) == str(event.id) for e in log)
        found = next(e for e in log if str(e.id) == str(event.id))
        assert found.action == "share_entry.created"
        assert found.event_metadata == {"split_type": "equal"}


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


def test_post_shared_entries_missing_fields(client) -> None:
    """POST /shared-entries without required fields returns 400."""
    _uid, token = _register_and_login(client)
    resp = client.post("/shared-entries", json={}, headers=_auth(token))
    assert resp.status_code == 400


def test_post_shared_entries_missing_fields_v2_contract(client) -> None:
    _uid, token = _register_and_login(client, "v2-shared")
    resp = client.post(
        "/shared-entries",
        json={},
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {
        "transaction_id": ["required"],
        "split_type": ["required"],
    }


def test_get_shared_entries_by_me_empty(client) -> None:
    """GET /shared-entries/by-me returns empty list for new user."""
    _uid, token = _register_and_login(client)
    resp = client.get("/shared-entries/by-me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["shared_entries"] == []


def test_get_shared_entries_with_me_empty(client) -> None:
    """GET /shared-entries/with-me returns empty list for new user."""
    _uid, token = _register_and_login(client)
    resp = client.get("/shared-entries/with-me", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["shared_entries"] == []


def test_get_invitations_empty(client) -> None:
    """GET /shared-entries/invitations returns empty list for new user."""
    _uid, token = _register_and_login(client)
    resp = client.get("/shared-entries/invitations", headers=_auth(token))
    assert resp.status_code == 200
    assert resp.get_json()["invitations"] == []


def test_post_invitation_missing_fields(client) -> None:
    """POST /shared-entries/invitations without required fields returns 400."""
    _uid, token = _register_and_login(client)
    resp = client.post("/shared-entries/invitations", json={}, headers=_auth(token))
    assert resp.status_code == 400


def test_post_invitation_missing_fields_v2_contract(client) -> None:
    _uid, token = _register_and_login(client, "v2-inv")
    resp = client.post(
        "/shared-entries/invitations",
        json={},
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert resp.status_code == 400
    body = resp.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {
        "shared_entry_id": ["required"],
        "invitee_email": ["required"],
    }


def test_accept_invitation_not_found(client) -> None:
    """POST /shared-entries/invitations/<bad-token>/accept returns 404."""
    _uid, token = _register_and_login(client)
    resp = client.post(
        "/shared-entries/invitations/nonexistent-token-xyz/accept",
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_delete_shared_entry_not_found(client) -> None:
    """DELETE /shared-entries/<uuid> for non-existent id returns 404."""
    _uid, token = _register_and_login(client)
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/shared-entries/{fake_id}", headers=_auth(token))
    assert resp.status_code == 404


def test_delete_invitation_not_found(client) -> None:
    """DELETE /shared-entries/invitations/<uuid> for non-existent id returns 404."""
    _uid, token = _register_and_login(client)
    fake_id = str(uuid.uuid4())
    resp = client.delete(f"/shared-entries/invitations/{fake_id}", headers=_auth(token))
    assert resp.status_code == 404


def test_shared_entry_requires_auth(client) -> None:
    """Endpoints require a valid JWT."""
    resp = client.get("/shared-entries/by-me")
    assert resp.status_code in (401, 422)
