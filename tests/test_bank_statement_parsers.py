from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.bank_statement_parsers import parse_nubank_csv, parse_ofx

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

OFX_2_SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
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

NUBANK_CSV_SAMPLE = """date,title,amount
2026-03-14,Supermercado,-123.45
2026-03-15,Salario,5000.00
""".strip()


def test_parse_ofx_1_sgml_extracts_transactions() -> None:
    entries = parse_ofx(OFX_1_SAMPLE, "itau")

    assert len(entries) == 2
    assert entries[0].external_id == "OFX-001"
    assert entries[0].date.isoformat() == "2026-03-15"
    assert entries[0].description == "Padaria Centro"
    assert entries[0].amount == Decimal("-150.45")
    assert entries[0].transaction_type == "expense"
    assert entries[0].bank_name == "itau"

    assert entries[1].external_id == "OFX-002"
    assert entries[1].description == "Recebimento Cliente"
    assert entries[1].transaction_type == "income"


def test_parse_ofx_2_xml_extracts_transactions() -> None:
    entries = parse_ofx(OFX_2_SAMPLE, "bb")

    assert len(entries) == 1
    assert entries[0].external_id == "BB-001"
    assert entries[0].date.isoformat() == "2026-03-17"
    assert entries[0].amount == Decimal("-89.90")
    assert entries[0].transaction_type == "expense"
    assert entries[0].bank_name == "bb"


def test_parse_ofx_rejects_unsupported_bank() -> None:
    with pytest.raises(ValueError, match="Unsupported OFX bank"):
        parse_ofx(OFX_1_SAMPLE, "nubank")


def test_parse_ofx_rejects_missing_transaction_blocks() -> None:
    with pytest.raises(ValueError, match="missing STMTTRN blocks"):
        parse_ofx("<OFX></OFX>", "caixa")


def test_parse_nubank_csv_extracts_transactions() -> None:
    entries = parse_nubank_csv(NUBANK_CSV_SAMPLE)

    assert len(entries) == 2
    assert entries[0].date.isoformat() == "2026-03-14"
    assert entries[0].description == "Supermercado"
    assert entries[0].amount == Decimal("-123.45")
    assert entries[0].transaction_type == "expense"
    assert entries[0].bank_name == "nubank"
    assert len(entries[0].external_id) == 16

    assert entries[1].description == "Salario"
    assert entries[1].transaction_type == "income"


def test_parse_nubank_csv_rejects_missing_required_header() -> None:
    invalid_csv = "date,amount\n2026-03-14,-10.00\n"

    with pytest.raises(ValueError, match="missing required columns: title"):
        parse_nubank_csv(invalid_csv)


def test_parse_nubank_csv_rejects_empty_rows() -> None:
    empty_csv = "date,title,amount\n"

    with pytest.raises(ValueError, match="has no transaction rows"):
        parse_nubank_csv(empty_csv)
