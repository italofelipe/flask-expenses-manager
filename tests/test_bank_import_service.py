from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.services.bank_import_service import BankImportService

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

NUBANK_CSV_WITH_DUPLICATE = """date,title,amount
2026-03-14,Supermercado,-123.45
2026-03-14,Supermercado,-123.45
""".strip()


def _create_user() -> User:
    suffix = uuid.uuid4().hex[:8]
    user = User(
        id=uuid.uuid4(),
        name=f"user-{suffix}",
        email=f"{suffix}@example.com",
        password="hash",
    )
    db.session.add(user)
    db.session.commit()
    return user


def _create_existing_transaction(*, user_id, external_id: str) -> Transaction:
    transaction = Transaction(
        user_id=user_id,
        title="Compra antiga",
        description="Transacao importada antes",
        amount=Decimal("150.45"),
        status=TransactionStatus.PAID,
        type=TransactionType.EXPENSE,
        due_date=date(2026, 3, 15),
        source="bank_import",
        external_id=external_id,
        bank_name="itau",
    )
    db.session.add(transaction)
    db.session.commit()
    return transaction


def test_build_preview_flags_existing_duplicates(app) -> None:
    with app.app_context():
        user = _create_user()
        _create_existing_transaction(user_id=user.id, external_id="OFX-001")

        service = BankImportService(user.id)
        result = service.build_preview(content=OFX_1_SAMPLE, bank_name="itau")

        assert result.bank_name == "itau"
        assert result.total_entries == 2
        assert result.duplicate_entries == 1
        assert result.new_entries == 1
        assert result.entries[0].external_id == "OFX-001"
        assert result.entries[0].is_duplicate is True
        assert result.entries[0].duplicate_reason == "existing_transaction"
        assert result.entries[1].external_id == "OFX-002"
        assert result.entries[1].is_duplicate is False


def test_build_preview_normalizes_bank_aliases(app) -> None:
    ofx_2_sample = """<?xml version="1.0" encoding="UTF-8"?>
<OFX>
  <BANKMSGSRSV1>
    <STMTTRNRS>
      <STMTRS>
        <BANKTRANLIST>
          <STMTTRN>
            <TRNTYPE>DEBIT</TRNTYPE>
            <DTPOSTED>20260317000000</DTPOSTED>
            <TRNAMT>-89.90</TRNAMT>
            <FITID>BB-001</FITID>
            <MEMO>Mercado Bairro</MEMO>
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""".strip()

    with app.app_context():
        user = _create_user()
        service = BankImportService(str(user.id))
        result = service.build_preview(
            content=ofx_2_sample,
            bank_name="Banco do Brasil",
        )

        assert result.bank_name == "bb"
        assert result.entries[0].bank_name == "bb"
        assert result.entries[0].description == "Mercado Bairro"


def test_build_preview_marks_duplicates_inside_same_file(app) -> None:
    with app.app_context():
        user = _create_user()
        service = BankImportService(user.id)
        result = service.build_preview(
            content=NUBANK_CSV_WITH_DUPLICATE,
            bank_name="nubank",
        )

        assert result.total_entries == 2
        assert result.duplicate_entries == 1
        assert result.new_entries == 1
        assert result.entries[0].is_duplicate is False
        assert result.entries[1].is_duplicate is True
        assert result.entries[1].duplicate_reason == "duplicate_in_file"


def test_build_preview_rejects_unsupported_bank(app) -> None:
    with app.app_context():
        user = _create_user()
        service = BankImportService(user.id)

        with pytest.raises(ValueError, match="Unsupported bank"):
            service.build_preview(content=OFX_1_SAMPLE, bank_name="inter")


def test_build_preview_rejects_empty_content(app) -> None:
    with app.app_context():
        user = _create_user()
        service = BankImportService(user.id)

        with pytest.raises(ValueError, match="cannot be empty"):
            service.build_preview(content="  \n ", bank_name="nubank")
