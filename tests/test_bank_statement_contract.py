from __future__ import annotations

import io
import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType

OFX_1_SAMPLE = """
OFXHEADER:100
DATA:OFXSGML
VERSION:102
SECURITY:NONE
ENCODING:USASCII
CHARSET:1252
COMPRESSION:NONE
OLDFILEUID:NONE
NEWFILEUID:NONE

<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT
            <DTPOSTED>20260315000000[-3:BRT]
            <TRNAMT>-150.45
            <FITID>OFX-001
            <MEMO>Padaria Centro
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20260316000000[-3:BRT]
            <TRNAMT>2500.00
            <FITID>OFX-002
            <NAME>Recebimento Cliente
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""".strip()

NUBANK_CSV = """date,title,amount
2026-03-14,Supermercado,-123.45
2026-03-15,Salario,5000.00
""".strip()


def _register_and_login(client, *, prefix: str = "bank-statement") -> str:
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


def _auth(token: str, contract: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _multipart_payload(content: str, *, filename: str, bank: str) -> dict[str, Any]:
    return {
        "bank": bank,
        "file": (io.BytesIO(content.encode("utf-8")), filename),
    }


def _create_existing_imported_transaction(app, *, user_id, external_id: str) -> None:
    with app.app_context():
        transaction = Transaction(
            user_id=user_id,
            title="Compra antiga",
            description="Transacao importada antes",
            amount=Decimal("150.45"),
            status=TransactionStatus.PAID,
            type=TransactionType.EXPENSE,
            due_date=date(2026, 3, 15),
            paid_at=None,
            source="bank_import",
            external_id=external_id,
            bank_name="itau",
        )
        db.session.add(transaction)
        db.session.commit()


def test_bank_statement_preview_legacy_contract(client) -> None:
    token = _register_and_login(client)

    response = client.post(
        "/bank-statements/preview",
        data=_multipart_payload(OFX_1_SAMPLE, filename="sample.ofx", bank="itau"),
        headers=_auth(token),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["message"] == "Preview gerado com sucesso"
    assert body["bank_name"] == "itau"
    assert body["total_entries"] == 2
    assert body["entries"][0]["external_id"] == "OFX-001"


def test_bank_statement_preview_v2_contract_marks_duplicates(client) -> None:
    token = _register_and_login(client, prefix="bank-statement-v2")
    from flask_jwt_extended import decode_token

    user_id = UUID(decode_token(token)["sub"])
    _create_existing_imported_transaction(
        client.application,
        user_id=user_id,
        external_id="OFX-001",
    )

    response = client.post(
        "/bank-statements/preview",
        data=_multipart_payload(OFX_1_SAMPLE, filename="sample.ofx", bank="itau"),
        headers=_auth(token, "v2"),
        content_type="multipart/form-data",
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["bank_name"] == "itau"
    assert body["data"]["duplicate_entries"] == 1
    assert body["data"]["entries"][0]["is_duplicate"] is True


def test_bank_statement_confirm_selective_persists_transactions(client) -> None:
    token = _register_and_login(client, prefix="bank-confirm")

    preview_response = client.post(
        "/bank-statements/preview",
        data=_multipart_payload(NUBANK_CSV, filename="nubank.csv", bank="nubank"),
        headers=_auth(token, "v2"),
        content_type="multipart/form-data",
    )
    assert preview_response.status_code == 200
    preview_entries = preview_response.get_json()["data"]["entries"]

    response = client.post(
        "/bank-statements/confirm",
        json={
            "bank": "nubank",
            "month": "2026-03",
            "mode": "selective",
            "transactions": [preview_entries[0]],
        },
        headers=_auth(token, "v2"),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["imported_count"] == 1
    assert body["data"]["skipped_duplicates"] == 0
    assert body["data"]["replaced_count"] == 0
    assert body["data"]["transactions"][0]["source"] == "bank_import"
    assert body["data"]["transactions"][0]["bank_name"] == "nubank"


def test_bank_statement_confirm_replace_month_replaces_prior_imports(client) -> None:
    token = _register_and_login(client, prefix="bank-replace")
    from flask_jwt_extended import decode_token

    user_id = UUID(decode_token(token)["sub"])
    _create_existing_imported_transaction(
        client.application,
        user_id=user_id,
        external_id="OFX-OLD-001",
    )

    preview_response = client.post(
        "/bank-statements/preview",
        data=_multipart_payload(OFX_1_SAMPLE, filename="sample.ofx", bank="itau"),
        headers=_auth(token, "v2"),
        content_type="multipart/form-data",
    )
    assert preview_response.status_code == 200
    preview_entries = preview_response.get_json()["data"]["entries"]

    response = client.post(
        "/bank-statements/confirm",
        json={
            "bank": "itau",
            "month": "2026-03",
            "mode": "replace_month",
            "transactions": preview_entries,
        },
        headers=_auth(token, "v2"),
    )

    assert response.status_code == 201
    body = response.get_json()
    assert body["data"]["replaced_count"] == 1
    assert body["data"]["imported_count"] == 2

    with client.application.app_context():
        rows = (
            Transaction.query.filter_by(user_id=user_id, deleted=False)
            .order_by(Transaction.external_id.asc())
            .all()
        )
        assert [row.external_id for row in rows] == ["OFX-001", "OFX-002"]


def test_bank_statement_confirm_rejects_month_mismatch(client) -> None:
    token = _register_and_login(client, prefix="bank-month")

    preview_response = client.post(
        "/bank-statements/preview",
        data=_multipart_payload(NUBANK_CSV, filename="nubank.csv", bank="nubank"),
        headers=_auth(token, "v2"),
        content_type="multipart/form-data",
    )
    assert preview_response.status_code == 200
    preview_entries = preview_response.get_json()["data"]["entries"]

    response = client.post(
        "/bank-statements/confirm",
        json={
            "bank": "nubank",
            "month": "2026-02",
            "mode": "selective",
            "transactions": preview_entries,
        },
        headers=_auth(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "BANK_IMPORT_CONFIRMATION_ERROR"
