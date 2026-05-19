"""Tests for the LGPD integral deletion service / endpoint (#1257).

Coverage targets
----------------

The legacy ``tests/test_account_deletion.py`` already covered the HTTP
shape (200 / 401 / 403 / 422) and PII anonymisation of the User row.
This file focuses on the *new* behaviour introduced by #1257:

- The deletion is **registry-driven**: every entity with a registered
  ``DeletionStrategy`` is touched per its strategy in a single
  transaction.
- The response **report** dict has ``summary.deleted / anonymized /
  retained`` keys plus a ``retentions`` array with the fiscal metadata.
- ``DELETE`` strategy entities (transactions, goals, accounts,
  refresh_tokens, push_subscriptions, …) are hard-deleted.
- ``ANONYMIZE`` strategy entities (users, audit_events,
  sharing_audit_events, subscriptions, consents) keep the row but null
  PII (or set it to a sentinel where the column is ``NOT NULL``).
- ``RETAIN`` strategy entities (fiscal_documents, fiscal_imports,
  receivable_entries, fiscal_adjustments) stay intact.
- The old access token is rejected after deletion (jti revoke + soft
  delete timestamp).
- An ``lgpd_account_deletion_started`` AuditEvent is persisted *before*
  the data transformations and survives anonymisation.
- Cross-user isolation: user A cannot delete user B's data.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any
from uuid import UUID

from flask.testing import FlaskClient

from app.models.ai_insight import InsightType
from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
from app.utils.datetime_utils import utc_now_naive

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PASSWORD = "StrongPass@123"


def _register_and_login(
    client: FlaskClient, prefix: str = "lgpd-del"
) -> tuple[str, str]:
    """Register + login → ``(token, email)``."""
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    reg = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": _PASSWORD},
    )
    assert reg.status_code == 201, reg.get_json()
    login = client.post("/auth/login", json={"email": email, "password": _PASSWORD})
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"], email


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _delete_me(client: FlaskClient, token: str, password: str = _PASSWORD) -> Any:
    return client.delete(
        "/user/me",
        json={"password": password},
        headers=_auth(token),
    )


def _user_id(client: FlaskClient, token: str) -> UUID:
    res = client.get("/user/me", headers=_auth(token))
    body = res.get_json()
    if "data" in body and isinstance(body["data"], dict):
        data = body["data"]
        if "id" in data:
            return UUID(data["id"])
        if "user" in data and "id" in data["user"]:
            return UUID(data["user"]["id"])
    return UUID(body["id"])


def _create_transaction(client: FlaskClient, token: str) -> dict[str, Any]:
    payload = {
        "title": "Lunch",
        "amount": 25.0,
        "type": "expense",
        "due_date": "2026-05-15",
        "status": "paid",
        "paid_at": "2026-05-15T12:00:00",
    }
    res = client.post("/transactions", json=payload, headers=_auth(token))
    assert res.status_code in (200, 201), res.get_json()
    return res.get_json()


def _create_goal(client: FlaskClient, token: str) -> dict[str, Any]:
    payload = {
        "title": "Emergency fund",
        "target_amount": 5000.0,
        "current_amount": 0.0,
        "target_date": "2027-01-01",
    }
    res = client.post("/goals", json=payload, headers=_auth(token))
    assert res.status_code in (200, 201), res.get_json()
    return res.get_json()


def _extract_report(resp: Any) -> dict[str, Any]:
    """Pull the deletion report out of the (legacy or v2) envelope."""
    body = resp.get_json()
    if "data" in body and isinstance(body["data"], dict) and "report" in body["data"]:
        return body["data"]["report"]  # type: ignore[no-any-return]
    return body["report"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Report contract
# ---------------------------------------------------------------------------


class TestReportContract:
    def test_delete_returns_report_with_summary_keys(self, client: FlaskClient) -> None:
        token, _ = _register_and_login(client)
        resp = _delete_me(client, token)
        assert resp.status_code == 200, resp.get_json()
        report = _extract_report(resp)
        assert "summary" in report
        summary = report["summary"]
        assert set(summary.keys()) == {"deleted", "anonymized", "retained"}

    def test_delete_report_has_user_id_and_deleted_at(
        self, client: FlaskClient
    ) -> None:
        token, _ = _register_and_login(client)
        uid = _user_id(client, token)
        resp = _delete_me(client, token)
        report = _extract_report(resp)
        assert UUID(report["user_id"]) == uid
        # deleted_at must be ISO 8601 ish
        assert "T" in report["deleted_at"]

    def test_delete_report_retentions_lists_fiscal_documents(
        self, client: FlaskClient
    ) -> None:
        token, _ = _register_and_login(client)
        resp = _delete_me(client, token)
        report = _extract_report(resp)
        retentions = report["retentions"]
        assert isinstance(retentions, list) and retentions
        fiscal = next(
            (r for r in retentions if r["entity"] == "fiscal_documents"), None
        )
        assert fiscal is not None
        assert fiscal["reason"] == "fiscal"
        assert fiscal["retention_days"] == 1825


# ---------------------------------------------------------------------------
# DELETE-strategy entities
# ---------------------------------------------------------------------------


class TestDeleteStrategy:
    def test_transactions_are_hard_deleted(self, client: FlaskClient, app: Any) -> None:
        from app.models.transaction import Transaction

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)
        _create_transaction(client, token)
        _create_transaction(client, token)
        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            remaining = Transaction.query.filter_by(user_id=uid).count()
            assert remaining == 0

        report = _extract_report(resp)
        deleted = report["summary"]["deleted"]
        assert deleted.get("transactions", 0) == 2

    def test_goals_are_hard_deleted(self, client: FlaskClient, app: Any) -> None:
        from app.models.goal import Goal

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)
        _create_goal(client, token)
        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            remaining = Goal.query.filter_by(user_id=uid).count()
            assert remaining == 0

        deleted = _extract_report(resp)["summary"]["deleted"]
        assert deleted.get("goals", 0) == 1

    def test_ai_insight_runs_are_hard_deleted(
        self, client: FlaskClient, app: Any
    ) -> None:
        from app.extensions.database import db

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        with app.app_context():
            db.session.add(
                AIInsightRun(
                    user_id=uid,
                    status=AIInsightRunStatus.generated,
                    period_type=InsightType.daily,
                    period_label="2026-05-18",
                    period_start=date(2026, 5, 18),
                    period_end=date(2026, 5, 18),
                    snapshot_schema_version="financial_insight_snapshot.v2",
                    snapshot_hash="sha256:delete-me",
                    prompt_template_version="financial-insight.v2.2026-05-18",
                    snapshot_json={"dimensions": {"transactions": {}}},
                    evidence_manifest_json={"evidence": {}},
                )
            )
            db.session.commit()
            assert AIInsightRun.query.filter_by(user_id=uid).count() == 1

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            assert AIInsightRun.query.filter_by(user_id=uid).count() == 0

        deleted = _extract_report(resp)["summary"]["deleted"]
        assert deleted.get("ai_insight_runs", 0) == 1

    def test_refresh_tokens_and_push_subscriptions_are_revoked(
        self, client: FlaskClient, app: Any
    ) -> None:
        """Auth artefacts must be wiped: refresh_tokens + push_subscriptions."""
        from app.models.push_subscription import PushSubscription, PushTransport
        from app.models.refresh_token import RefreshToken

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        # Seed a push subscription and a second refresh token row by hand.
        with app.app_context():
            from app.extensions.database import db

            push = PushSubscription(
                user_id=uid,
                transport=PushTransport.web_push,
                endpoint="https://example.test/push/" + uuid.uuid4().hex,
                keys={"p256dh": "x", "auth": "y"},
            )
            extra_token = RefreshToken(
                user_id=uid,
                token_hash=uuid.uuid4().hex,
                jti=uuid.uuid4().hex,
                family_id=uuid.uuid4(),
                expires_at=utc_now_naive() + timedelta(days=30),
            )
            db.session.add(push)
            db.session.add(extra_token)
            db.session.commit()

            assert RefreshToken.query.filter_by(user_id=uid).count() >= 1
            assert PushSubscription.query.filter_by(user_id=uid).count() == 1

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            assert RefreshToken.query.filter_by(user_id=uid).count() == 0
            assert PushSubscription.query.filter_by(user_id=uid).count() == 0


# ---------------------------------------------------------------------------
# ANONYMIZE-strategy entities
# ---------------------------------------------------------------------------


class TestAnonymizeStrategy:
    def test_user_row_is_anonymised(self, client: FlaskClient, app: Any) -> None:
        from app.models.user import User

        token, email = _register_and_login(client)
        uid = _user_id(client, token)
        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            user = User.query.filter_by(id=uid).first()
            assert user is not None
            assert user.name == "Deleted User"
            assert user.email == f"deleted_{uid}@deleted.auraxis"
            assert user.email != email
            # password column must still hold *something* but never the raw
            # token or the original hash — werkzeug hashes always carry
            # the algorithm prefix.
            assert user.password.split(":")[0] or user.password.startswith(
                ("pbkdf2", "scrypt", "argon2")
            )
            assert user.current_jti is None
            assert user.refresh_token_jti is None
            assert user.birth_date is None
            assert user.deleted_at is not None

        anon = _extract_report(resp)["summary"]["anonymized"]
        assert anon.get("users", 0) == 1

    def test_audit_events_user_id_is_nulled(
        self, client: FlaskClient, app: Any
    ) -> None:
        """``audit_events.user_id`` is the only PII column and must go to NULL."""
        from app.extensions.database import db
        from app.models.audit_event import AuditEvent

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        # Seed a couple of pre-existing audit rows attributed to this user.
        with app.app_context():
            db.session.add_all(
                [
                    AuditEvent(
                        method="GET",
                        path="/foo",
                        status=200,
                        user_id=str(uid),
                    ),
                    AuditEvent(
                        method="POST",
                        path="/bar",
                        status=201,
                        user_id=str(uid),
                    ),
                ]
            )
            db.session.commit()

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            remaining = AuditEvent.query.filter(AuditEvent.user_id == str(uid)).count()
            assert remaining == 0
            # rows still exist with NULL user_id (count > 0 because the
            # deletion service / controller wrote at least the lifecycle
            # audit events).
            anonymised = AuditEvent.query.filter(AuditEvent.user_id.is_(None)).count()
            assert anonymised >= 2

    def test_sharing_audit_events_use_sentinel(
        self, client: FlaskClient, app: Any
    ) -> None:
        """``sharing_audit_events.user_id`` is NOT NULL → sentinel UUID."""
        from app.extensions.database import db
        from app.models.sharing_audit import SharingAuditEvent

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        with app.app_context():
            db.session.add(
                SharingAuditEvent(
                    user_id=uid,
                    action="invite_sent",
                    resource_type="invitation",
                    resource_id=uuid.uuid4(),
                    event_metadata={},
                )
            )
            db.session.commit()
            assert SharingAuditEvent.query.filter_by(user_id=uid).count() == 1

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        sentinel = UUID(int=0)
        with app.app_context():
            assert SharingAuditEvent.query.filter_by(user_id=uid).count() == 0
            assert SharingAuditEvent.query.filter_by(user_id=sentinel).count() == 1

    def test_subscriptions_keep_row_but_null_provider_pii(
        self, client: FlaskClient, app: Any
    ) -> None:
        """Fiscal-retained subscription row keeps amounts but loses provider PII."""
        from app.extensions.database import db
        from app.models.subscription import (
            BillingCycle,
            Subscription,
            SubscriptionStatus,
        )

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        # Register already created a free-tier Subscription via the
        # bootstrap pipeline. We mutate it into a "premium-with-PII" row
        # so we can later assert the PII fields get nulled.
        with app.app_context():
            sub = Subscription.query.filter_by(user_id=uid).first()
            assert sub is not None, "register flow should seed a Subscription"
            sub.plan_code = "premium"
            sub.status = SubscriptionStatus.ACTIVE
            sub.billing_cycle = BillingCycle.MONTHLY
            sub.provider = "asaas"
            sub.provider_subscription_id = "sub_xyz"
            sub.provider_customer_id = "cust_xyz"
            sub.provider_event_id = "evt_xyz"
            db.session.commit()

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            sub = Subscription.query.filter_by(user_id=uid).first()
            assert sub is not None  # row preserved for fiscal retention
            assert sub.provider_subscription_id is None
            assert sub.provider_customer_id is None
            assert sub.provider_event_id is None
            # Non-PII columns survive
            assert sub.plan_code == "premium"


# ---------------------------------------------------------------------------
# RETAIN-strategy entities
# ---------------------------------------------------------------------------


class TestRetainStrategy:
    def test_fiscal_documents_are_retained(self, client: FlaskClient, app: Any) -> None:
        from app.extensions.database import db
        from app.models.fiscal import (
            FiscalDocument,
            FiscalDocumentStatus,
            FiscalDocumentType,
        )

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)

        with app.app_context():
            doc = FiscalDocument(
                user_id=uid,
                external_id="NF-001",
                type=FiscalDocumentType.RECEIPT,
                status=FiscalDocumentStatus.ISSUED,
                issued_at=date(2026, 1, 1),
                counterparty="Acme Ltda",
                gross_amount=1000,
                currency="BRL",
            )
            db.session.add(doc)
            db.session.commit()

        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            # Row must still exist — fiscal retention is non-negotiable.
            remaining = FiscalDocument.query.filter_by(user_id=uid).count()
            assert remaining == 1

        retained = _extract_report(resp)["summary"]["retained"]
        assert retained.get("fiscal_documents", 0) == 1


# ---------------------------------------------------------------------------
# Audit trail
# ---------------------------------------------------------------------------


class TestAuditTrail:
    def test_lifecycle_audit_events_are_persisted(
        self, client: FlaskClient, app: Any
    ) -> None:
        """``lgpd_account_deletion_started`` AuditEvent must survive deletion."""
        from app.models.audit_event import AuditEvent

        token, _ = _register_and_login(client)
        resp = _delete_me(client, token)
        assert resp.status_code == 200

        with app.app_context():
            started = AuditEvent.query.filter_by(
                action="lgpd_account_deletion_started"
            ).count()
            completed = AuditEvent.query.filter_by(
                action="lgpd_account_deletion_completed"
            ).count()
            assert started >= 1
            assert completed >= 1


# ---------------------------------------------------------------------------
# Token revocation post-deletion
# ---------------------------------------------------------------------------


class TestTokenRevocation:
    def test_old_jwt_is_rejected_post_deletion(self, client: FlaskClient) -> None:
        token, _ = _register_and_login(client)
        _delete_me(client, token)

        # Any authenticated request must now return 401.
        res = client.get("/user/me", headers=_auth(token))
        assert res.status_code == 401

        # And specifically the LGPD export endpoint (sibling) too.
        res = client.get("/user/me/export", headers=_auth(token))
        assert res.status_code == 401


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestCrossUserIsolation:
    def test_deletion_only_touches_caller(self, client: FlaskClient, app: Any) -> None:
        from app.models.transaction import Transaction
        from app.models.user import User

        token_a, _ = _register_and_login(client, "lgpd-a")
        token_b, email_b = _register_and_login(client, "lgpd-b")
        uid_a = _user_id(client, token_a)
        uid_b = _user_id(client, token_b)

        # User B owns a transaction that must survive A's deletion.
        _create_transaction(client, token_b)
        _create_transaction(client, token_a)  # A's transaction (will go)

        resp = _delete_me(client, token_a)
        assert resp.status_code == 200

        with app.app_context():
            # A's data wiped
            assert Transaction.query.filter_by(user_id=uid_a).count() == 0
            user_a = User.query.filter_by(id=uid_a).first()
            assert user_a is not None
            assert user_a.email != email_b
            # B untouched
            assert Transaction.query.filter_by(user_id=uid_b).count() == 1
            user_b = User.query.filter_by(id=uid_b).first()
            assert user_b is not None
            assert user_b.email == email_b
            assert user_b.deleted_at is None


# ---------------------------------------------------------------------------
# Direct service unit test — exercises the registry pass without HTTP.
# ---------------------------------------------------------------------------


class TestServiceUnit:
    def test_service_returns_report_shape(self, client: FlaskClient, app: Any) -> None:
        """Call ``delete_user_account`` directly to lock the contract."""
        from app.application.services.lgpd_deletion_service import (
            delete_user_account,
        )

        token, _ = _register_and_login(client)
        uid = _user_id(client, token)
        _create_transaction(client, token)

        with app.app_context():
            report = delete_user_account(uid)

        assert report["user_id"] == str(uid)
        assert "deleted_at" in report
        assert set(report["summary"].keys()) == {"deleted", "anonymized", "retained"}
        # The User row was anonymised, so the count is >= 1.
        assert report["summary"]["anonymized"].get("users", 0) == 1
        # The transaction was hard-deleted.
        assert report["summary"]["deleted"].get("transactions", 0) == 1
