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


def test_revoke_share_sets_status_declined(app) -> None:
    """Revoking a shared entry sets its status to DECLINED."""
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
            split_type="custom",
        )
        revoked = revoke_share(shared_entry_id=entry.id, owner_id=owner.id)
        assert revoked.status == SharedEntryStatus.DECLINED


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


def test_post_shared_entries_invalid_split_type_v2_contract(client) -> None:
    _uid, token = _register_and_login(client, "v2-shared-invalid-split")
    response = client.post(
        "/shared-entries",
        json={
            "transaction_id": str(uuid.uuid4()),
            "split_type": "invalid",
        },
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {
        "split_type": ["must_be_one_of: equal, percentage, custom"],
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


def test_post_invitation_invalid_expiration_v2_contract(client) -> None:
    _uid, token = _register_and_login(client, "v2-inv-invalid-exp")
    response = client.post(
        "/shared-entries/invitations",
        json={
            "shared_entry_id": str(uuid.uuid4()),
            "invitee_email": "invitee@test.com",
            "expires_in_hours": "oops",
        },
        headers={**_auth(token), "X-API-Contract": "v2"},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["error"]["details"] == {
        "expires_in_hours": ["must_be_integer"],
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


# ---------------------------------------------------------------------------
# Serializer unit tests — enriched fields
# ---------------------------------------------------------------------------


def _make_shared_entry(owner, txn, split_type: str = "equal"):
    """Return a SharedEntry (not persisted) with the transaction relationship set."""
    from app.models.shared_entry import SharedEntry, SharedEntryStatus, SplitType
    from app.utils.datetime_utils import utc_now_naive

    entry = SharedEntry(
        id=uuid.uuid4(),
        owner_id=owner.id,
        transaction_id=txn.id,
        split_type=SplitType(split_type),
        status=SharedEntryStatus.PENDING,
        created_at=utc_now_naive(),
        updated_at=utc_now_naive(),
    )
    # Attach the transaction object directly (simulating lazy="joined")
    entry.transaction = txn
    entry.invitations = []
    return entry


def test_serialize_shared_entry_includes_transaction_fields(app) -> None:
    """Serializer exposes transaction_title and transaction_amount."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry

    with app.app_context():
        owner = _make_user("ser-txn")
        txn = _make_transaction(owner.id)

        entry = _make_shared_entry(owner, txn, split_type="equal")
        payload = serialize_shared_entry(entry)

        assert payload["transaction_title"] == txn.title
        assert payload["transaction_amount"] == float(txn.amount)


def test_serialize_my_share_equal_split(app) -> None:
    """my_share for split_type=equal is amount/2."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry

    with app.app_context():
        owner = _make_user("ser-eq")
        txn = _make_transaction(owner.id)  # amount=100

        entry = _make_shared_entry(owner, txn, split_type="equal")
        payload = serialize_shared_entry(entry)

        assert payload["my_share"] == 50.0


def test_serialize_my_share_percentage_split(app) -> None:
    """my_share for split_type=percentage is amount * split_value/100."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry
    from app.models.shared_entry import Invitation, InvitationStatus
    from app.utils.datetime_utils import utc_now_naive

    with app.app_context():
        owner = _make_user("ser-pct")
        txn = _make_transaction(owner.id)  # amount=100

        entry = _make_shared_entry(owner, txn, split_type="percentage")

        inv = Invitation(
            id=uuid.uuid4(),
            shared_entry_id=entry.id,
            from_user_id=owner.id,
            to_user_email="invitee@test.com",
            split_value=30,  # 30%
            share_amount=None,
            status=InvitationStatus.ACCEPTED,
            created_at=utc_now_naive(),
        )
        entry.invitations = [inv]

        payload = serialize_shared_entry(entry)
        assert payload["my_share"] == pytest.approx(30.0)


def test_serialize_my_share_custom_split(app) -> None:
    """my_share for split_type=custom is the fixed share_amount."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry
    from app.models.shared_entry import Invitation, InvitationStatus
    from app.utils.datetime_utils import utc_now_naive

    with app.app_context():
        owner = _make_user("ser-cst")
        txn = _make_transaction(owner.id)  # amount=100

        entry = _make_shared_entry(owner, txn, split_type="custom")

        inv = Invitation(
            id=uuid.uuid4(),
            shared_entry_id=entry.id,
            from_user_id=owner.id,
            to_user_email="invitee@test.com",
            split_value=None,
            share_amount=40,
            status=InvitationStatus.ACCEPTED,
            created_at=utc_now_naive(),
        )
        entry.invitations = [inv]

        payload = serialize_shared_entry(entry)
        assert payload["my_share"] == pytest.approx(40.0)


def test_serialize_other_party_email(app) -> None:
    """other_party_email comes from the first invitation's to_user_email."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry
    from app.models.shared_entry import Invitation, InvitationStatus
    from app.utils.datetime_utils import utc_now_naive

    with app.app_context():
        owner = _make_user("ser-ope")
        txn = _make_transaction(owner.id)

        entry = _make_shared_entry(owner, txn, split_type="equal")

        inv = Invitation(
            id=uuid.uuid4(),
            shared_entry_id=entry.id,
            from_user_id=owner.id,
            to_user_email="partner@test.com",
            split_value=None,
            share_amount=None,
            status=InvitationStatus.ACCEPTED,
            created_at=utc_now_naive(),
        )
        entry.invitations = [inv]

        payload = serialize_shared_entry(entry)
        assert payload["other_party_email"] == "partner@test.com"


# ---------------------------------------------------------------------------
# Integration tests — GET /shared-entries/by-me and /with-me enriched fields
# ---------------------------------------------------------------------------


def _create_transaction_via_api(client, token: str) -> str:
    """Helper: create a transaction and return its id."""
    from datetime import date

    resp = client.post(
        "/transactions",
        json={
            "title": "Shared Txn",
            "amount": 200.0,
            "type": "EXPENSE",
            "due_date": str(date(2026, 6, 1)),
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    # The transactions endpoint returns {transaction: [<obj>]} (list with one item)
    txn_value = body.get("transaction") or body.get("data", {}).get("transaction")
    if isinstance(txn_value, list) and txn_value:
        return str(txn_value[0]["id"])
    if isinstance(txn_value, dict):
        return str(txn_value["id"])
    raise AssertionError(f"Could not extract transaction id from response: {body}")


def test_get_shared_entries_by_me_has_enriched_fields(client) -> None:
    """GET /shared-entries/by-me returns transaction_title, transaction_amount, my_share."""  # noqa: E501
    owner_id, owner_token = _register_and_login(client, "enrich-own")
    txn_id = _create_transaction_via_api(client, owner_token)

    # Create shared entry
    resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 201, resp.get_json()

    # List
    list_resp = client.get("/shared-entries/by-me", headers=_auth(owner_token))
    assert list_resp.status_code == 200
    entries = list_resp.get_json()["shared_entries"]
    assert len(entries) >= 1
    entry = next(e for e in entries if e["transaction_id"] == txn_id)

    assert entry["transaction_title"] == "Shared Txn"
    assert entry["transaction_amount"] == pytest.approx(200.0)
    assert entry["my_share"] == pytest.approx(100.0)  # equal split: 200/2
    assert entry["status"] in ("pending", "accepted", "declined")
    assert entry["split_type"] == "equal"


def test_get_shared_entries_with_me_has_enriched_fields(client) -> None:
    """GET /shared-entries/with-me returns enriched fields from invitee perspective."""
    suffix = uuid.uuid4().hex[:6]
    invitee_email = f"j13-enrich-wi-inv-{suffix}@test.com"

    owner_id, owner_token = _register_and_login(client, f"wim-own-{suffix}")
    # Register invitee with a known email so we can use it directly
    inv_password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={
            "name": f"wim-inv-{suffix}",
            "email": invitee_email,
            "password": inv_password,
        },
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post(
        "/auth/login", json={"email": invitee_email, "password": inv_password}
    )
    assert login.status_code == 200, login.get_json()
    invitee_token: str = login.get_json()["token"]

    txn_id = _create_transaction_via_api(client, owner_token)

    # Owner creates shared entry
    resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 201, resp.get_json()
    se_body = resp.get_json()
    shared_entry_id = se_body.get("shared_entry", {}).get("id") or se_body.get(
        "data", {}
    ).get("shared_entry", {}).get("id")

    # Owner sends invitation
    inv_resp = client.post(
        "/shared-entries/invitations",
        json={"shared_entry_id": shared_entry_id, "invitee_email": invitee_email},
        headers=_auth(owner_token),
    )
    assert inv_resp.status_code == 201, inv_resp.get_json()
    inv_body = inv_resp.get_json()
    token_val = inv_body.get("invitation", {}).get("token") or inv_body.get(
        "data", {}
    ).get("invitation", {}).get("token")

    # Invitee accepts
    accept_resp = client.post(
        f"/shared-entries/invitations/{token_val}/accept",
        headers=_auth(invitee_token),
    )
    assert accept_resp.status_code == 200, accept_resp.get_json()

    # Invitee lists /with-me
    with_me_resp = client.get("/shared-entries/with-me", headers=_auth(invitee_token))
    assert with_me_resp.status_code == 200
    entries = with_me_resp.get_json()["shared_entries"]
    assert len(entries) >= 1
    entry = next(e for e in entries if e["transaction_id"] == txn_id)

    assert entry["transaction_title"] == "Shared Txn"
    assert entry["transaction_amount"] == pytest.approx(200.0)
    assert entry["my_share"] == pytest.approx(100.0)  # equal split


def test_enum_values_aligned_with_frontend(app) -> None:
    """Status and split_type enum values match what the frontend expects."""
    from app.models.shared_entry import SharedEntryStatus, SplitType

    with app.app_context():
        assert {s.value for s in SharedEntryStatus} == {
            "pending",
            "accepted",
            "declined",
        }
        assert {s.value for s in SplitType} == {"equal", "percentage", "custom"}


# ---------------------------------------------------------------------------
# Optimistic locking — service unit tests (#1053)
# ---------------------------------------------------------------------------


def test_update_shared_entry_increments_version(app) -> None:
    """update_shared_entry increments version and applies split_type change."""
    from app.extensions.database import db
    from app.models.shared_entry import SplitType
    from app.services.shared_entry_service import share_entry, update_shared_entry

    with app.app_context():
        owner = _make_user("upd-ok")
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id, transaction_id=txn.id, split_type="equal"
        )
        assert entry.version == 0

        updated = update_shared_entry(
            entry.id,
            owner.id,
            expected_version=0,
            split_type="percentage",
        )
        assert updated.version == 1
        assert updated.split_type == SplitType.PERCENTAGE


def test_update_shared_entry_concurrent_edit_raises_conflict(app) -> None:
    """update_shared_entry raises SharedEntryConcurrentEditError on version mismatch."""
    from app.extensions.database import db
    from app.services.shared_entry_service import (
        SharedEntryConcurrentEditError,
        share_entry,
        update_shared_entry,
    )

    with app.app_context():
        owner = _make_user("upd-conflict")
        db.session.add(owner)
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id, transaction_id=txn.id, split_type="equal"
        )
        # Advance version once legitimately
        update_shared_entry(entry.id, owner.id, expected_version=0)

        # Now try to update with the stale version (0 instead of 1)
        with pytest.raises(SharedEntryConcurrentEditError):
            update_shared_entry(entry.id, owner.id, expected_version=0)


def test_update_shared_entry_not_found_raises(app) -> None:
    """update_shared_entry raises SharedEntryNotFoundError for unknown id."""
    import uuid

    from app.services.shared_entry_service import (
        SharedEntryNotFoundError,
        update_shared_entry,
    )

    with app.app_context():
        with pytest.raises(SharedEntryNotFoundError):
            update_shared_entry(uuid.uuid4(), uuid.uuid4(), expected_version=0)


def test_update_shared_entry_forbidden_raises(app) -> None:
    """update_shared_entry raises SharedEntryForbiddenError for non-owner."""
    from app.extensions.database import db
    from app.services.shared_entry_service import (
        SharedEntryForbiddenError,
        share_entry,
        update_shared_entry,
    )

    with app.app_context():
        owner = _make_user("upd-owner")
        attacker = _make_user("upd-atk")
        db.session.add_all([owner, attacker])
        db.session.flush()
        txn = _make_transaction(owner.id)
        db.session.add(txn)
        db.session.commit()

        entry = share_entry(
            owner_id=owner.id, transaction_id=txn.id, split_type="equal"
        )

        with pytest.raises(SharedEntryForbiddenError):
            update_shared_entry(entry.id, attacker.id, expected_version=0)


# ---------------------------------------------------------------------------
# Optimistic locking — serializer unit test (#1053)
# ---------------------------------------------------------------------------


def test_serialize_shared_entry_includes_version(app) -> None:
    """serialize_shared_entry exposes the version field."""
    from app.controllers.shared_entries.serializers import serialize_shared_entry

    with app.app_context():
        owner = _make_user("ser-ver")
        txn = _make_transaction(owner.id)

        entry = _make_shared_entry(owner, txn, split_type="equal")
        entry.version = 3  # type: ignore[assignment]

        payload = serialize_shared_entry(entry)
        assert payload["version"] == 3


# ---------------------------------------------------------------------------
# Optimistic locking — HTTP endpoint tests (#1053)
# ---------------------------------------------------------------------------


def test_patch_shared_entry_success(client) -> None:
    """PATCH /shared-entries/<id> with correct version updates the entry."""
    owner_id, owner_token = _register_and_login(client, "patch-ok")
    txn_id = _create_transaction_via_api(client, owner_token)

    create_resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert create_resp.status_code == 201, create_resp.get_json()
    body = create_resp.get_json()
    se = body.get("shared_entry") or body.get("data", {}).get("shared_entry", {})
    se_id = se["id"]
    assert se["version"] == 0

    patch_resp = client.patch(
        f"/shared-entries/{se_id}",
        json={"version": 0, "split_type": "percentage"},
        headers=_auth(owner_token),
    )
    assert patch_resp.status_code == 200, patch_resp.get_json()
    updated = patch_resp.get_json()
    updated_se = updated.get("shared_entry") or updated.get("data", {}).get(
        "shared_entry", {}
    )
    assert updated_se["version"] == 1
    assert updated_se["split_type"] == "percentage"


def test_patch_shared_entry_missing_version_returns_400(client) -> None:
    """PATCH without 'version' returns 400."""
    owner_id, owner_token = _register_and_login(client, "patch-no-ver")
    txn_id = _create_transaction_via_api(client, owner_token)

    create_resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.get_json()
    se = body.get("shared_entry") or body.get("data", {}).get("shared_entry", {})
    se_id = se["id"]

    resp = client.patch(
        f"/shared-entries/{se_id}",
        json={"split_type": "custom"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 400


def test_patch_shared_entry_invalid_version_returns_400(client) -> None:
    """PATCH with non-integer 'version' returns 400."""
    owner_id, owner_token = _register_and_login(client, "patch-bad-ver")
    txn_id = _create_transaction_via_api(client, owner_token)

    create_resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.get_json()
    se = body.get("shared_entry") or body.get("data", {}).get("shared_entry", {})
    se_id = se["id"]

    resp = client.patch(
        f"/shared-entries/{se_id}",
        json={"version": "not-a-number"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 400


def test_patch_shared_entry_invalid_split_type_returns_400(client) -> None:
    """PATCH with invalid split_type returns 400."""
    owner_id, owner_token = _register_and_login(client, "patch-bad-st")
    txn_id = _create_transaction_via_api(client, owner_token)

    create_resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.get_json()
    se = body.get("shared_entry") or body.get("data", {}).get("shared_entry", {})
    se_id = se["id"]

    resp = client.patch(
        f"/shared-entries/{se_id}",
        json={"version": 0, "split_type": "invalid_type"},
        headers=_auth(owner_token),
    )
    assert resp.status_code == 400


def test_patch_shared_entry_not_found_returns_404(client) -> None:
    """PATCH /shared-entries/<unknown-uuid> returns 404."""
    _uid, token = _register_and_login(client, "patch-404")
    fake_id = str(uuid.uuid4())

    resp = client.patch(
        f"/shared-entries/{fake_id}",
        json={"version": 0},
        headers=_auth(token),
    )
    assert resp.status_code == 404


def test_patch_shared_entry_concurrent_edit_returns_409(client) -> None:
    """PATCH with stale version returns 409 CONFLICT_CONCURRENT_EDIT."""
    owner_id, owner_token = _register_and_login(client, "patch-409")
    txn_id = _create_transaction_via_api(client, owner_token)

    create_resp = client.post(
        "/shared-entries",
        json={"transaction_id": txn_id, "split_type": "equal"},
        headers=_auth(owner_token),
    )
    assert create_resp.status_code == 201
    body = create_resp.get_json()
    se = body.get("shared_entry") or body.get("data", {}).get("shared_entry", {})
    se_id = se["id"]

    # First update succeeds (version 0 → 1)
    first = client.patch(
        f"/shared-entries/{se_id}",
        json={"version": 0, "split_type": "percentage"},
        headers=_auth(owner_token),
    )
    assert first.status_code == 200

    # Second update with stale version 0 must conflict
    second = client.patch(
        f"/shared-entries/{se_id}",
        json={"version": 0, "split_type": "custom"},
        headers=_auth(owner_token),
    )
    assert second.status_code == 409
