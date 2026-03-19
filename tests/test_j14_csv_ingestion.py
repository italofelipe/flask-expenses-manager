"""Tests for J14-2 — Generic CSV ingestion and receivable/fiscal services.

Covers:
- parse_csv_generic with sample CSV content
- ingest_as_receivables creates correct records
- POST /fiscal/csv/upload returns preview without persisting
- POST /fiscal/csv/confirm persists records
- GET /fiscal/receivables/summary returns correct totals
- PATCH /fiscal/receivables/<id>/receive updates status
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Dict

# ---------------------------------------------------------------------------
# Auth helpers (shared with other contract tests)
# ---------------------------------------------------------------------------


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    reg = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201

    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth(token: str) -> Dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# CSV content fixtures
# ---------------------------------------------------------------------------

SAMPLE_CSV = """description,amount,date,category
Consultoria Técnica,1500.00,2025-01-15,services
Manutenção Servidor,800.50,2025-01-20,infrastructure
Desenvolvimento Software,3200.00,2025-02-01,services
"""

SAMPLE_CSV_BR_FORMAT = """Descrição,Valor,Data,Categoria
Consultoria Técnica,1.500,00,15/01/2025,serviços
Manutenção Servidor,800,50,20/01/2025,infraestrutura
"""

SAMPLE_COLUMN_MAP = {
    "description": "description",
    "amount": "amount",
    "date": "date",
    "category": "category",
}


# ---------------------------------------------------------------------------
# Unit tests — csv_ingestion_service
# ---------------------------------------------------------------------------


class TestParseCsvGeneric:
    def test_parses_standard_csv_correctly(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        result = parse_csv_generic(SAMPLE_CSV, SAMPLE_COLUMN_MAP)

        assert len(result.rows) == 3
        assert len(result.errors) == 0

    def test_first_row_values(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        result = parse_csv_generic(SAMPLE_CSV, SAMPLE_COLUMN_MAP)
        first = result.rows[0]

        assert first.description == "Consultoria Técnica"
        assert first.amount == Decimal("1500.00")
        assert str(first.date) == "2025-01-15"
        assert first.category == "services"

    def test_parses_all_rows(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        result = parse_csv_generic(SAMPLE_CSV, SAMPLE_COLUMN_MAP)
        amounts = [r.amount for r in result.rows]

        assert Decimal("1500.00") in amounts
        assert Decimal("800.50") in amounts
        assert Decimal("3200.00") in amounts

    def test_custom_column_map(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        csv_content = "desc,val,dt\nPagamento,500.00,2025-03-01\n"
        col_map = {"desc": "description", "val": "amount", "dt": "date"}
        result = parse_csv_generic(csv_content, col_map)

        assert len(result.rows) == 1
        assert result.rows[0].description == "Pagamento"
        assert result.rows[0].amount == Decimal("500.00")

    def test_missing_required_field_goes_to_errors(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        # amount column missing from map
        col_map = {"description": "description", "date": "date"}
        result = parse_csv_generic(SAMPLE_CSV, col_map)

        assert len(result.errors) == 3
        assert len(result.rows) == 0

    def test_invalid_amount_goes_to_errors(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        csv_content = "description,amount,date\nTest,NOT_A_NUMBER,2025-01-01\n"
        result = parse_csv_generic(csv_content, SAMPLE_COLUMN_MAP)

        assert len(result.errors) == 1
        assert (
            "amount" in result.errors[0]["error"].lower()
            or "parse" in result.errors[0]["error"].lower()
        )

    def test_empty_csv_returns_empty_result(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        result = parse_csv_generic("description,amount,date\n", SAMPLE_COLUMN_MAP)

        assert result.rows == []
        assert result.errors == []

    def test_external_id_is_captured(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        csv_content = (
            "description,amount,date,external_id\nPagamento,100.00,2025-01-01,EXT-001\n"
        )
        col_map = {
            "description": "description",
            "amount": "amount",
            "date": "date",
            "external_id": "external_id",
        }
        result = parse_csv_generic(csv_content, col_map)

        assert len(result.rows) == 1
        assert result.rows[0].external_id == "EXT-001"

    def test_date_br_format(self) -> None:
        from app.services.csv_ingestion_service import parse_csv_generic

        csv_content = "description,amount,date\nPagamento,100.00,15/03/2025\n"
        result = parse_csv_generic(csv_content, SAMPLE_COLUMN_MAP)

        assert len(result.rows) == 1
        assert result.rows[0].date.year == 2025
        assert result.rows[0].date.month == 3
        assert result.rows[0].date.day == 15


class TestIngestAsReceivables:
    def test_creates_fiscal_documents_and_entries(self, app) -> None:
        from datetime import date

        from app.extensions.database import db
        from app.models.fiscal import (
            FiscalDocument,
            ReceivableEntry,
            ReconciliationStatus,
        )
        from app.services.csv_ingestion_service import ParsedRow, ingest_as_receivables

        with app.app_context():
            # Create a real user via auth
            from app.models.user import User

            user_uuid = uuid.uuid4()
            user_id = str(user_uuid)
            user = User(
                id=user_uuid,
                name="Test User",
                email=f"test-{user_id[:8]}@test.com",
                password="hash",
            )
            db.session.add(user)
            db.session.commit()

            rows = [
                ParsedRow(
                    description="Serviço A",
                    amount=Decimal("1000.00"),
                    date=date(2025, 1, 10),
                    category="services",
                    external_id="EXT-001",
                ),
                ParsedRow(
                    description="Serviço B",
                    amount=Decimal("500.00"),
                    date=date(2025, 2, 5),
                ),
            ]

            created = ingest_as_receivables(user_id, rows)

            assert len(created) == 2
            docs = FiscalDocument.query.filter_by(user_id=user_uuid).all()
            assert len(docs) == 2

            entries = ReceivableEntry.query.filter_by(user_id=user_uuid).all()
            assert len(entries) == 2
            for entry in entries:
                assert entry.reconciliation_status == ReconciliationStatus.PENDING

    def test_deduplicates_by_external_id(self, app) -> None:
        from datetime import date

        from app.extensions.database import db
        from app.models.fiscal import FiscalDocument
        from app.services.csv_ingestion_service import ParsedRow, ingest_as_receivables

        with app.app_context():
            from app.models.user import User

            user_uuid = uuid.uuid4()
            user_id = str(user_uuid)
            user = User(
                id=user_uuid,
                name="Test User",
                email=f"test-dup-{user_id[:8]}@test.com",
                password="hash",
            )
            db.session.add(user)
            db.session.commit()

            rows = [
                ParsedRow(
                    description="Serviço",
                    amount=Decimal("1000.00"),
                    date=date(2025, 1, 10),
                    external_id="SAME-ID",
                ),
            ]
            created_first = ingest_as_receivables(user_id, rows)
            assert len(created_first) == 1

            # Second call with same external_id — should be skipped
            created_second = ingest_as_receivables(user_id, rows)
            assert len(created_second) == 0

            docs = FiscalDocument.query.filter_by(user_id=user_uuid).all()
            assert len(docs) == 1


# ---------------------------------------------------------------------------
# Integration tests — HTTP endpoints
# ---------------------------------------------------------------------------


class TestCsvUploadEndpoint:
    def test_upload_returns_preview_without_persisting(self, client, app) -> None:
        token = _register_and_login(client, prefix="csv-upload")

        resp = client.post(
            "/fiscal/csv/upload",
            json={"content": SAMPLE_CSV, "column_map": SAMPLE_COLUMN_MAP},
            headers=_auth(token),
        )

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["valid_rows"] == 3
        assert len(body["preview"]) == 3
        assert body["error_rows"] == 0

    def test_upload_preview_does_not_persist(self, client, app) -> None:
        token = _register_and_login(client, prefix="csv-no-persist")

        client.post(
            "/fiscal/csv/upload",
            json={"content": SAMPLE_CSV, "column_map": SAMPLE_COLUMN_MAP},
            headers=_auth(token),
        )

        # Fetch receivables — should be empty since upload only previews
        list_resp = client.get("/fiscal/receivables", headers=_auth(token))
        assert list_resp.status_code == 200
        body = list_resp.get_json()
        assert body["count"] == 0

    def test_upload_without_content_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="csv-no-content")

        resp = client.post(
            "/fiscal/csv/upload",
            json={},
            headers=_auth(token),
        )

        assert resp.status_code == 400

    def test_upload_requires_auth(self, client) -> None:
        resp = client.post("/fiscal/csv/upload", json={"content": SAMPLE_CSV})
        assert resp.status_code == 401


class TestCsvConfirmEndpoint:
    def test_confirm_persists_records(self, client, app) -> None:
        token = _register_and_login(client, prefix="csv-confirm")

        resp = client.post(
            "/fiscal/csv/confirm",
            json={"content": SAMPLE_CSV, "column_map": SAMPLE_COLUMN_MAP},
            headers=_auth(token),
        )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["imported_count"] == 3
        assert body["error_rows"] == 0

    def test_confirm_records_visible_in_list(self, client, app) -> None:
        token = _register_and_login(client, prefix="csv-visible")

        client.post(
            "/fiscal/csv/confirm",
            json={"content": SAMPLE_CSV, "column_map": SAMPLE_COLUMN_MAP},
            headers=_auth(token),
        )

        list_resp = client.get("/fiscal/receivables", headers=_auth(token))
        assert list_resp.status_code == 200
        body = list_resp.get_json()
        assert body["count"] == 3

    def test_confirm_without_content_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="csv-confirm-err")

        resp = client.post(
            "/fiscal/csv/confirm",
            json={},
            headers=_auth(token),
        )

        assert resp.status_code == 400


class TestReceivablesEndpoints:
    def test_create_manual_receivable(self, client) -> None:
        token = _register_and_login(client, prefix="recv-create")

        resp = client.post(
            "/fiscal/receivables",
            json={
                "description": "Pagamento consultoria",
                "amount": "2500.00",
                "expected_date": "2025-03-15",
                "category": "consulting",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 201
        body = resp.get_json()
        assert body["receivable"]["reconciliation_status"] == "pending"
        assert "disclaimer" in body["receivable"]

    def test_create_receivable_missing_fields(self, client) -> None:
        token = _register_and_login(client, prefix="recv-missing")

        resp = client.post(
            "/fiscal/receivables",
            json={"description": "Missing amount"},
            headers=_auth(token),
        )

        assert resp.status_code == 400

    def test_list_receivables_empty(self, client) -> None:
        token = _register_and_login(client, prefix="recv-empty")

        resp = client.get("/fiscal/receivables", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 0
        assert body["receivables"] == []

    def test_list_receivables_status_filter(self, client) -> None:
        token = _register_and_login(client, prefix="recv-filter")

        # Create one receivable
        client.post(
            "/fiscal/receivables",
            json={
                "description": "Serviço filtro",
                "amount": "1000.00",
                "expected_date": "2025-03-01",
            },
            headers=_auth(token),
        )

        # Filter pending — should find it
        resp = client.get("/fiscal/receivables?status=pending", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.get_json()["count"] == 1

        # Filter received — should be empty
        resp_received = client.get(
            "/fiscal/receivables?status=received", headers=_auth(token)
        )
        assert resp_received.status_code == 200
        assert resp_received.get_json()["count"] == 0

    def test_mark_received_updates_status(self, client) -> None:
        token = _register_and_login(client, prefix="recv-receive")

        create_resp = client.post(
            "/fiscal/receivables",
            json={
                "description": "Pagamento a receber",
                "amount": "1500.00",
                "expected_date": "2025-03-10",
            },
            headers=_auth(token),
        )
        assert create_resp.status_code == 201
        entry_id = create_resp.get_json()["receivable"]["id"]

        patch_resp = client.patch(
            f"/fiscal/receivables/{entry_id}/receive",
            json={"received_date": "2025-03-12"},
            headers=_auth(token),
        )

        assert patch_resp.status_code == 200
        body = patch_resp.get_json()
        assert body["receivable"]["reconciliation_status"] == "reconciled"
        assert body["receivable"]["received_at"] is not None

    def test_mark_received_requires_date(self, client) -> None:
        token = _register_and_login(client, prefix="recv-no-date")

        create_resp = client.post(
            "/fiscal/receivables",
            json={
                "description": "Pagamento",
                "amount": "100.00",
                "expected_date": "2025-01-01",
            },
            headers=_auth(token),
        )
        entry_id = create_resp.get_json()["receivable"]["id"]

        resp = client.patch(
            f"/fiscal/receivables/{entry_id}/receive",
            json={},
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_mark_received_not_found(self, client) -> None:
        token = _register_and_login(client, prefix="recv-notfound")
        fake_id = str(uuid.uuid4())

        resp = client.patch(
            f"/fiscal/receivables/{fake_id}/receive",
            json={"received_date": "2025-01-01"},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_cancel_receivable(self, client) -> None:
        token = _register_and_login(client, prefix="recv-cancel")

        create_resp = client.post(
            "/fiscal/receivables",
            json={
                "description": "A cancelar",
                "amount": "700.00",
                "expected_date": "2025-04-01",
            },
            headers=_auth(token),
        )
        entry_id = create_resp.get_json()["receivable"]["id"]

        del_resp = client.delete(
            f"/fiscal/receivables/{entry_id}",
            headers=_auth(token),
        )
        assert del_resp.status_code == 200
        assert del_resp.get_json()["receivable"]["reconciliation_status"] == "partial"


class TestRevenueSummary:
    def test_summary_returns_correct_totals(self, client) -> None:
        token = _register_and_login(client, prefix="summary-test")

        # Create two receivables
        client.post(
            "/fiscal/receivables",
            json={
                "description": "A",
                "amount": "1000.00",
                "expected_date": "2025-01-01",
            },
            headers=_auth(token),
        )
        create_resp = client.post(
            "/fiscal/receivables",
            json={
                "description": "B",
                "amount": "2000.00",
                "expected_date": "2025-02-01",
            },
            headers=_auth(token),
        )
        entry_b_id = create_resp.get_json()["receivable"]["id"]

        # Mark B as received
        client.patch(
            f"/fiscal/receivables/{entry_b_id}/receive",
            json={"received_date": "2025-02-15"},
            headers=_auth(token),
        )

        resp = client.get("/fiscal/receivables/summary", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.get_json()
        summary = body.get("summary") or body  # supports both v1 and v2

        assert Decimal(summary["expected_total"]) == Decimal("3000.00")
        assert Decimal(summary["received_total"]) == Decimal("2000.00")
        assert Decimal(summary["pending_total"]) == Decimal("1000.00")
        assert "disclaimer" in summary

    def test_summary_empty_user(self, client) -> None:
        token = _register_and_login(client, prefix="summary-empty")

        resp = client.get("/fiscal/receivables/summary", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.get_json()
        summary = body.get("summary") or body
        assert Decimal(summary["expected_total"]) == Decimal("0")
        assert Decimal(summary["received_total"]) == Decimal("0")
        assert Decimal(summary["pending_total"]) == Decimal("0")


class TestFiscalDocumentsEndpoints:
    def test_create_fiscal_document(self, client) -> None:
        token = _register_and_login(client, prefix="fiscal-doc-create")

        resp = client.post(
            "/fiscal/fiscal-documents",
            json={
                "type": "service_invoice",
                "amount": "5000.00",
                "issued_at": "2025-01-20",
                "counterpart_name": "Cliente ACME",
            },
            headers=_auth(token),
        )

        assert resp.status_code == 201
        body = resp.get_json()
        doc = body["fiscal_document"]
        assert doc["type"] == "service_invoice"
        assert doc["gross_amount"] == "5000.00"
        assert doc["counterparty"] == "Cliente ACME"

    def test_list_fiscal_documents(self, client) -> None:
        token = _register_and_login(client, prefix="fiscal-doc-list")

        client.post(
            "/fiscal/fiscal-documents",
            json={"type": "receipt", "amount": "100.00", "issued_at": "2025-01-01"},
            headers=_auth(token),
        )

        resp = client.get("/fiscal/fiscal-documents", headers=_auth(token))

        assert resp.status_code == 200
        body = resp.get_json()
        assert body["count"] == 1

    def test_create_invalid_type_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="fiscal-invalid-type")

        resp = client.post(
            "/fiscal/fiscal-documents",
            json={
                "type": "invalid_type",
                "amount": "100.00",
                "issued_at": "2025-01-01",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_create_missing_fields_returns_400(self, client) -> None:
        token = _register_and_login(client, prefix="fiscal-missing")

        resp = client.post(
            "/fiscal/fiscal-documents",
            json={"type": "receipt"},
            headers=_auth(token),
        )
        assert resp.status_code == 400
