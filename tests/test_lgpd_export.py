"""Tests for the LGPD data export endpoint (#1256).

Coverage targets:

- GET /user/me/export requires auth (401 without token)
- Returns metadata block with scope, registry_version, user_id, generated_at
- Includes the User row in the ``users`` section
- Includes any consents the user has registered
- Includes the user's transactions
- Cross-user isolation: A's data never leaks into B's export
- Retentions section lists fiscal_documents with reason ``fiscal`` and 1825 days
- Entities flagged ``export_included=False`` (refresh_tokens, llm_audit_logs,
  alerts, push_subscriptions, entitlements, audit_events,
  sharing_audit_events) are absent from the package
- UUIDs are serialised as strings
- Datetimes are serialised as ISO-8601 strings
- Enum columns are serialised by ``.value`` (lowercase)
- Direct service call exercises the same contract without HTTP
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

import pytest
from flask import Flask
from flask.testing import FlaskClient

from app.application.services.lgpd_export_service import (
    _serialize_row,
    _serialize_value,
    build_user_export,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ISO_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:[+-]\d{2}:\d{2}|Z)?$"
)


def _register_and_login(client: FlaskClient, prefix: str = "lgpd-exp") -> str:
    """Register + login → return Bearer token string."""
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    register = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201, register.get_json()
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.get_json()
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _resolve_user_id(client: FlaskClient, token: str) -> UUID:
    """Read the authenticated user's id from /user/me."""
    res = client.get("/user/me", headers=_auth(token))
    body = res.get_json()
    if "data" in body and isinstance(body["data"], dict):
        data = body["data"]
        if "id" in data:
            return UUID(data["id"])
        if "user" in data and "id" in data["user"]:
            return UUID(data["user"]["id"])
    return UUID(body["id"])


def _export(client: FlaskClient, token: str) -> dict[str, object]:
    res = client.get("/user/me/export", headers=_auth(token))
    assert res.status_code == 200, res.get_json()
    body = res.get_json()
    assert "data" in body, body
    return body["data"]  # type: ignore[no-any-return]


# ---------------------------------------------------------------------------
# Auth + metadata
# ---------------------------------------------------------------------------


class TestAuthAndMetadata:
    def test_export_requires_auth(self, client: FlaskClient) -> None:
        res = client.get("/user/me/export")
        assert res.status_code in {401, 422}

    def test_export_metadata_present(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        meta = package["metadata"]  # type: ignore[index]
        assert isinstance(meta, dict)
        assert meta["scope"] == "lgpd_full_export"
        assert meta["registry_version"] == "1.0"
        assert _ISO_RE.match(str(meta["generated_at"]))
        # user_id must be a valid UUID string
        UUID(str(meta["user_id"]))

    def test_export_metadata_user_id_matches_caller(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        expected = _resolve_user_id(client, token)
        package = _export(client, token)
        meta = package["metadata"]  # type: ignore[index]
        assert str(meta["user_id"]) == str(expected)  # type: ignore[index]


# ---------------------------------------------------------------------------
# Entity coverage
# ---------------------------------------------------------------------------


class TestEntityCoverage:
    def test_empty_user_returns_metadata_and_user_row(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        # User row is always present (single-element list).
        assert isinstance(package["users"], list)
        assert len(package["users"]) == 1  # type: ignore[arg-type]
        # Untouched arrays for other entities.
        assert package["transactions"] == []
        assert package["goals"] == []
        # Retentions is always present even with no rows owned.
        assert isinstance(package["retentions"], list)

    def test_export_includes_user_profile(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        users = package["users"]
        assert isinstance(users, list) and len(users) == 1
        user_row = users[0]
        assert "id" in user_row
        assert "email" in user_row
        assert "name" in user_row
        # ``created_at`` is a non-null DateTime column — its presence proves
        # the row was serialised from real column metadata rather than from
        # a hand-curated subset.
        assert "created_at" in user_row

    def test_export_includes_consents(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        # Record two consents.
        for kind in ("terms", "privacy"):
            res = client.post(
                "/me/consents",
                json={
                    "kind": kind,
                    "version": "1.0",
                    "action": "granted",
                    "source": "web",
                },
                headers=_auth(token),
            )
            assert res.status_code == 201, res.get_json()
        package = _export(client, token)
        consents = package["consents"]
        assert isinstance(consents, list)
        kinds = {row["kind"] for row in consents}
        assert {"terms", "privacy"} <= kinds


# ---------------------------------------------------------------------------
# Cross-user isolation
# ---------------------------------------------------------------------------


class TestUserIsolation:
    def test_export_only_returns_caller_data(self, client: FlaskClient) -> None:
        token_a = _register_and_login(client, "lgpd-exp-a")
        token_b = _register_and_login(client, "lgpd-exp-b")
        # User A records a consent. User B must not see it.
        res_a = client.post(
            "/me/consents",
            json={
                "kind": "ai",
                "version": "1.0",
                "action": "granted",
                "source": "web",
            },
            headers=_auth(token_a),
        )
        assert res_a.status_code == 201
        user_b_id = _resolve_user_id(client, token_b)
        package_b = _export(client, token_b)
        # User B's consents must be empty.
        assert package_b["consents"] == []
        # Metadata user_id must be B's id, not A's.
        meta = package_b["metadata"]  # type: ignore[index]
        assert str(meta["user_id"]) == str(user_b_id)  # type: ignore[index]


# ---------------------------------------------------------------------------
# Retentions section
# ---------------------------------------------------------------------------


class TestRetentions:
    def test_retentions_section_includes_fiscal_documents(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        retentions = package["retentions"]
        assert isinstance(retentions, list)
        entries_by_entity = {row["entity"]: row for row in retentions}
        fiscal = entries_by_entity.get("fiscal_documents")
        assert fiscal is not None, retentions
        assert fiscal["reason"] == "fiscal"
        assert fiscal["retention_days"] == 1825
        assert "tax" in fiscal["explanation"].lower()

    def test_retentions_section_lists_all_retain_entities(
        self, client: FlaskClient
    ) -> None:
        from app.lgpd import REGISTRY, DeletionStrategy

        token = _register_and_login(client)
        package = _export(client, token)
        retentions = package["retentions"]
        retained_tables = {row["entity"] for row in retentions}  # type: ignore[union-attr]
        registry_retained = {
            rule.table_name
            for rule in REGISTRY
            if rule.deletion_strategy == DeletionStrategy.RETAIN
        }
        assert retained_tables == registry_retained


# ---------------------------------------------------------------------------
# Excluded entities
# ---------------------------------------------------------------------------


class TestExcludedEntities:
    def test_export_does_not_include_refresh_tokens(self, client: FlaskClient) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        assert "refresh_tokens" not in package
        assert "llm_audit_logs" not in package
        assert "audit_events" not in package
        assert "alerts" not in package
        assert "push_subscriptions" not in package
        assert "entitlements" not in package
        assert "sharing_audit_events" not in package


class TestSensitiveColumnsExcluded:
    """LGPD export must NEVER leak credentials / session-token columns even
    for the requesting user — exposing the bcrypt hash or JTI has no LGPD
    upside and creates an unnecessary attack surface.
    """

    def test_user_row_omits_password_and_token_columns(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client)
        package = _export(client, token)
        users = package["users"]
        assert len(users) == 1
        user_row = users[0]
        sensitive = {
            "password",
            "current_jti",
            "refresh_token_jti",
            "password_reset_token_hash",
            "password_reset_token_expires_at",
            "password_reset_requested_at",
            "email_verification_token_hash",
            "email_verification_token_expires_at",
        }
        leaked = sensitive & set(user_row)
        assert not leaked, f"Sensitive columns leaked in LGPD export: {leaked}"

    def test_user_row_keeps_non_sensitive_pii(self, client: FlaskClient) -> None:
        """Non-sensitive PII (name, email, profile) MUST stay — that is the
        whole point of LGPD portability.
        """
        token = _register_and_login(client)
        package = _export(client, token)
        user_row = package["users"][0]
        assert "id" in user_row
        assert "email" in user_row
        assert "name" in user_row


class TestRemappedColumnNames:
    """Regression: Simulation declares ``extra_metadata = db.Column("metadata", …)``
    so the Python attribute name and DB column name diverge. A naive
    ``getattr(row, col.name)`` returns the SQLAlchemy reserved ``Base.metadata``
    object and crashes the JSON encoder. The mapper-based serializer must
    read via the Python attribute name and emit under the DB column name.
    """

    def test_simulation_with_metadata_column_serialises_cleanly(
        self, app: Flask, client: FlaskClient
    ) -> None:
        from app.extensions.database import db as _db
        from app.models.simulation import Simulation

        token = _register_and_login(client)
        # Resolve current user id via /user/me to keep this test free of any
        # internal helper coupling.
        me_resp = client.get("/user/me", headers={"Authorization": f"Bearer {token}"})
        assert me_resp.status_code == 200
        user_id_str = (me_resp.get_json().get("data") or me_resp.get_json())["user"][
            "id"
        ]

        with app.app_context():
            sim = Simulation(
                user_id=UUID(user_id_str),
                tool_id="salary_net",
                rule_version="1.0",
                inputs={"gross": 5000},
                result={"net": 4200},
                extra_metadata={"label": "Cenário conservador"},
            )
            _db.session.add(sim)
            _db.session.commit()

        package = _export(client, token)
        sims = package["simulations"]
        assert len(sims) == 1
        row = sims[0]
        # The DB column is `metadata`; the export must report it under that
        # name and the value must be the dict we stored (not SQLAlchemy's
        # MetaData object).
        assert "metadata" in row
        assert row["metadata"] == {"label": "Cenário conservador"}


# ---------------------------------------------------------------------------
# Serialiser primitives (unit-level)
# ---------------------------------------------------------------------------


class _Colour(Enum):
    RED = "red"
    BLUE = "blue"


class TestSerialiserPrimitives:
    def test_serialize_uuid_returns_string(self) -> None:
        value = UUID("11111111-1111-1111-1111-111111111111")
        assert _serialize_value(value) == "11111111-1111-1111-1111-111111111111"

    def test_serialize_datetime_returns_iso_with_offset(self) -> None:
        naive = datetime(2026, 5, 17, 12, 0, 0)
        rendered = _serialize_value(naive)
        assert isinstance(rendered, str)
        assert rendered.endswith("+00:00")
        aware = datetime(2026, 5, 17, 12, 0, 0, tzinfo=UTC)
        assert _serialize_value(aware) == "2026-05-17T12:00:00+00:00"

    def test_serialize_enum_returns_value(self) -> None:
        assert _serialize_value(_Colour.RED) == "red"

    def test_serialize_decimal_returns_string(self) -> None:
        assert _serialize_value(Decimal("12.34")) == "12.34"

    def test_serialize_none_returns_none(self) -> None:
        assert _serialize_value(None) is None

    def test_serialize_bytes_returns_hex(self) -> None:
        assert _serialize_value(b"\x00\x01\x02") == "000102"

    def test_serialize_date_returns_iso(self) -> None:
        from datetime import date

        assert _serialize_value(date(2026, 5, 17)) == "2026-05-17"

    def test_iso_helper_handles_none(self) -> None:
        from app.application.services.lgpd_export_service import _iso

        assert _iso(None) is None

    def test_serialize_row_uses_column_metadata(self, client: FlaskClient) -> None:
        """End-to-end check that _serialize_row converts a real model row."""
        token = _register_and_login(client, "lgpd-exp-row")
        from app.models.user import User

        user = User.query.filter_by(name=re.split(r"@", token, maxsplit=1)[0]).first()
        # Fallback: fetch the first User created (test isolation per-test
        # via the autouse db fixture).
        if user is None:
            user = User.query.first()
        assert user is not None
        serialised = _serialize_row(user)
        # ``id`` is a UUID column → must be string.
        assert isinstance(serialised["id"], str)
        UUID(serialised["id"])
        # Created_at should be ISO.
        assert serialised["created_at"] is None or _ISO_RE.match(
            str(serialised["created_at"])
        )


# ---------------------------------------------------------------------------
# Service-level direct call
# ---------------------------------------------------------------------------


@pytest.mark.usefixtures("app")
class TestServiceDirect:
    def test_build_user_export_for_unknown_user_returns_metadata_only(self) -> None:
        """Service must not crash for a non-existent user.

        The User row simply comes back as empty list. All other entities
        also have zero rows. The package shape stays consistent.
        """
        package = build_user_export(uuid.uuid4())
        assert package["metadata"]["scope"] == "lgpd_full_export"  # type: ignore[index]
        assert package["users"] == []
        # Retentions never depends on user data.
        assert len(package["retentions"]) >= 1  # type: ignore[arg-type]
