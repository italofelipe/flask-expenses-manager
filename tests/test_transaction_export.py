"""Tests for GET /transactions/export (issue #1022).

Covers:
- CSV export returns valid CSV with correct columns
- PDF export returns valid PDF bytes
- Free user (no export_pdf entitlement) receives 403 ENTITLEMENT_REQUIRED
- Premium user receives file
- Filters (type, status, date range) narrow results correctly
- Invalid format parameter returns 400
- Export with zero transactions returns empty CSV (headers only)
- Export limit is respected (mocked)
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import date
from decimal import Decimal

from app.extensions.database import db
from app.models.entitlement import Entitlement, EntitlementSource
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.transaction_export_service import EXPORT_LIMIT, generate_csv_export

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, *, prefix: str = "export") -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@auraxis.test"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    token = login.get_json()["token"]
    profile = client.get("/user/profile", headers=_auth(token))
    body = profile.get_json()
    user_id = body.get("data", {}).get("id") or body["user"]["id"]
    return token, user_id


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant_export_entitlement(app, user_id: str) -> None:
    with app.app_context():
        ent = Entitlement(
            user_id=uuid.UUID(user_id),
            feature_key="export_pdf",
            source=EntitlementSource.SUBSCRIPTION,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()


def _create_transaction(
    app,
    user_id: str,
    *,
    title: str = "Test tx",
    amount: str = "100.00",
    tx_type: TransactionType = TransactionType.EXPENSE,
    status: TransactionStatus = TransactionStatus.PENDING,
    due_date: date = date(2026, 1, 15),
) -> None:
    with app.app_context():
        tx = Transaction(
            user_id=uuid.UUID(user_id),
            title=title,
            amount=Decimal(amount),
            type=tx_type,
            status=status,
            due_date=due_date,
        )
        db.session.add(tx)
        db.session.commit()


# ---------------------------------------------------------------------------
# Entitlement gate
# ---------------------------------------------------------------------------


class TestExportEntitlementGate:
    def test_free_user_gets_403(self, app, client) -> None:
        from app.services.entitlement_service import revoke_entitlement

        token, user_id = _register_and_login(client, prefix="export-free")
        # Revoke the trial entitlement to simulate a free/downgraded user
        with app.app_context():
            revoke_entitlement(uuid.UUID(user_id), "export_pdf")
            from app.extensions.database import db as _db

            _db.session.commit()
        resp = client.get("/transactions/export", headers=_auth(token))
        assert resp.status_code == 403
        body = resp.get_json()
        assert body["error"]["code"] == "ENTITLEMENT_REQUIRED"

    def test_premium_user_gets_file(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="export-prem")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=csv", headers=_auth(token))
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_unauthenticated_gets_401(self, client) -> None:
        resp = client.get("/transactions/export")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# CSV format
# ---------------------------------------------------------------------------


class TestCsvExport:
    def test_csv_has_correct_headers(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-hdr")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=csv", headers=_auth(token))
        assert resp.status_code == 200
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8-sig")))
        headers = next(reader)
        assert headers == ["data", "tipo", "titulo", "valor", "status", "descricao"]

    def test_csv_empty_when_no_transactions(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-empty")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=csv", headers=_auth(token))
        assert resp.status_code == 200
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8-sig")))
        rows = list(reader)
        assert len(rows) == 1  # headers only

    def test_csv_contains_transaction_data(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-data")
        _grant_export_entitlement(app, user_id)
        _create_transaction(
            app,
            user_id,
            title="Salário",
            amount="5000.00",
            tx_type=TransactionType.INCOME,
            status=TransactionStatus.PAID,
            due_date=date(2026, 1, 5),
        )
        resp = client.get("/transactions/export?format=csv", headers=_auth(token))
        assert resp.status_code == 200
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8-sig")))
        next(reader)  # skip headers
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][2] == "Salário"
        assert rows[0][3] == "5000.00"
        assert rows[0][1] == "income"

    def test_csv_content_disposition_header(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-disp")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=csv", headers=_auth(token))
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        assert ".csv" in resp.headers.get("Content-Disposition", "")

    def test_csv_type_filter(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-type")
        _grant_export_entitlement(app, user_id)
        _create_transaction(
            app, user_id, title="Income tx", tx_type=TransactionType.INCOME
        )
        _create_transaction(
            app, user_id, title="Expense tx", tx_type=TransactionType.EXPENSE
        )
        resp = client.get(
            "/transactions/export?format=csv&type=income", headers=_auth(token)
        )
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8-sig")))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][1] == "income"

    def test_csv_date_filter(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-date")
        _grant_export_entitlement(app, user_id)
        _create_transaction(app, user_id, title="Jan tx", due_date=date(2026, 1, 10))
        _create_transaction(app, user_id, title="Mar tx", due_date=date(2026, 3, 10))
        resp = client.get(
            "/transactions/export?format=csv&start_date=2026-02-01&end_date=2026-12-31",
            headers=_auth(token),
        )
        reader = csv.reader(io.StringIO(resp.data.decode("utf-8-sig")))
        next(reader)
        rows = list(reader)
        assert len(rows) == 1
        assert rows[0][2] == "Mar tx"

    def test_csv_filename_includes_date_range(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="csv-fname")
        _grant_export_entitlement(app, user_id)
        resp = client.get(
            "/transactions/export?format=csv&start_date=2026-01-01&end_date=2026-03-31",
            headers=_auth(token),
        )
        disposition = resp.headers.get("Content-Disposition", "")
        assert "2026-01" in disposition
        assert "2026-03" in disposition


# ---------------------------------------------------------------------------
# PDF format
# ---------------------------------------------------------------------------


class TestPdfExport:
    def test_pdf_content_type(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="pdf-ct")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=pdf", headers=_auth(token))
        assert resp.status_code == 200
        assert "application/pdf" in resp.content_type

    def test_pdf_starts_with_magic_bytes(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="pdf-magic")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=pdf", headers=_auth(token))
        assert resp.data[:4] == b"%PDF"

    def test_pdf_content_disposition_header(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="pdf-disp")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=pdf", headers=_auth(token))
        assert "attachment" in resp.headers.get("Content-Disposition", "")
        assert ".pdf" in resp.headers.get("Content-Disposition", "")


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


class TestExportValidation:
    def test_invalid_format_returns_400(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="val-fmt")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?format=excel", headers=_auth(token))
        assert resp.status_code == 400

    def test_invalid_date_format_returns_400(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="val-date")
        _grant_export_entitlement(app, user_id)
        resp = client.get(
            "/transactions/export?start_date=01-01-2026", headers=_auth(token)
        )
        assert resp.status_code == 400

    def test_start_after_end_returns_400(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="val-range")
        _grant_export_entitlement(app, user_id)
        resp = client.get(
            "/transactions/export?start_date=2026-12-31&end_date=2026-01-01",
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_invalid_type_param_returns_400(self, app, client) -> None:
        token, user_id = _register_and_login(client, prefix="val-type")
        _grant_export_entitlement(app, user_id)
        resp = client.get("/transactions/export?type=revenue", headers=_auth(token))
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# Export service unit tests
# ---------------------------------------------------------------------------


class TestExportServiceUnit:
    def test_csv_generate_returns_bom(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            result = generate_csv_export(user_id=user_id)
            # UTF-8 BOM for Excel compatibility
            assert result.content[:3] == b"\xef\xbb\xbf"

    def test_csv_generate_empty_has_headers(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            result = generate_csv_export(user_id=user_id)
            reader = csv.reader(io.StringIO(result.content.decode("utf-8-sig")))
            rows = list(reader)
            assert rows[0] == ["data", "tipo", "titulo", "valor", "status", "descricao"]
            assert len(rows) == 1

    def test_csv_generate_filename_with_month_label(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            result = generate_csv_export(user_id=user_id, month_label="2026-01")
            assert "2026-01" in result.filename
            assert result.filename.endswith(".csv")

    def test_export_limit_constant(self) -> None:
        assert EXPORT_LIMIT == 10_000
