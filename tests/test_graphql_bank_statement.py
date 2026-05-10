"""GraphQL tests for Bank Statement Import domain (#1148)."""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient

# ---------------------------------------------------------------------------
# Sample bank statement content (reuses constants from the REST contract tests)
# ---------------------------------------------------------------------------

NUBANK_CSV = """date,title,amount
2026-03-14,Supermercado,-123.45
2026-03-15,Salario,5000.00
""".strip()

OFX_ITAU = """
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
            <FITID>OFX-GQL-001
            <MEMO>Padaria Centro
          </STMTTRN>
          <STMTTRN>
            <TRNTYPE>CREDIT
            <DTPOSTED>20260316000000[-3:BRT]
            <TRNAMT>2500.00
            <FITID>OFX-GQL-002
            <NAME>Recebimento Cliente
          </STMTTRN>
        </BANKTRANLIST>
      </STMTRS>
    </STMTTRNRS>
  </BANKMSGSRSV1>
</OFX>
""".strip()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client: FlaskClient, prefix: str = "gql-bs") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201
    r2 = client.post("/auth/login", json={"email": email, "password": password})
    assert r2.status_code == 200
    return r2.get_json()["token"]


def _gql(
    client: FlaskClient,
    query: str,
    variables: dict | None = None,
    token: str | None = None,
) -> dict:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    res = client.post(
        "/graphql", json={"query": query, "variables": variables or {}}, headers=headers
    )
    assert res.status_code in {200, 401}
    if res.status_code == 401:
        return {
            "errors": [
                {"message": "Unauthorized", "extensions": {"code": "UNAUTHORIZED"}}
            ]
        }
    return res.get_json()


# ---------------------------------------------------------------------------
# GraphQL documents
# ---------------------------------------------------------------------------

_PREVIEW_BANK_STATEMENT = """
mutation PreviewBankStatement($content: String!, $bankName: String!) {
  previewBankStatement(content: $content, bankName: $bankName) {
    ok
    message
    errors { field message }
    data {
      bankName
      totalEntries
      duplicateEntries
      newEntries
      entries {
        externalId
        date
        description
        amount
        transactionType
        bankName
        isDuplicate
        duplicateReason
      }
    }
  }
}
"""

_CONFIRM_BANK_IMPORT = """
mutation ConfirmBankImport(
  $bankName: String!
  $month: String!
  $mode: String!
  $selectedEntries: [SelectedEntryInput!]!
) {
  confirmBankImport(
    bankName: $bankName
    month: $month
    mode: $mode
    selectedEntries: $selectedEntries
  ) {
    ok
    message
    errors { field message }
    bankName
    month
    importedCount
    skippedDuplicates
    replacedCount
    transactions {
      id
      title
      amount
      type
      dueDate
      bankName
      externalId
    }
  }
}
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestPreviewBankStatementMutation:
    def test_preview_nubank_csv_returns_entries(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "bs-preview-nu")
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": NUBANK_CSV, "bankName": "nubank"},
            token,
        )
        assert "errors" not in body, body.get("errors")
        payload = body["data"]["previewBankStatement"]
        assert payload["ok"] is True
        data = payload["data"]
        assert data["bankName"] == "nubank"
        assert data["totalEntries"] == 2
        assert data["duplicateEntries"] == 0
        assert data["newEntries"] == 2
        assert len(data["entries"]) == 2

    def test_preview_ofx_returns_entries(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "bs-preview-ofx")
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": OFX_ITAU, "bankName": "itau"},
            token,
        )
        assert "errors" not in body, body.get("errors")
        payload = body["data"]["previewBankStatement"]
        assert payload["ok"] is True
        assert payload["data"]["totalEntries"] == 2

    def test_preview_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": NUBANK_CSV, "bankName": "nubank"},
        )
        assert "errors" in body
        code = (
            body["errors"][0].get("extensions", {}).get("code")
            or body["errors"][0]["message"]
        )
        assert (
            "UNAUTHORIZED" in str(code).upper()
            or "GRAPHQL_AUTH_REQUIRED" in str(code).upper()
        )

    def test_preview_invalid_bank_returns_validation_error(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "bs-preview-inv")
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": "any content", "bankName": "unknown_bank"},
            token,
        )
        assert "errors" in body
        code = body["errors"][0]["extensions"]["code"]
        assert code == "VALIDATION_ERROR"

    def test_preview_empty_content_returns_validation_error(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "bs-preview-empty")
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": "   ", "bankName": "nubank"},
            token,
        )
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_preview_marks_duplicate_entries(self, client: FlaskClient) -> None:
        """A CSV with the same FITID/external_id twice should show duplicates."""
        duplicate_csv = """date,title,amount
2026-03-14,Supermercado,-123.45
2026-03-14,Supermercado,-123.45
""".strip()
        token = _register_and_login(client, "bs-preview-dup")
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": duplicate_csv, "bankName": "nubank"},
            token,
        )
        assert "errors" not in body, body.get("errors")
        data = body["data"]["previewBankStatement"]["data"]
        # Nubank CSV generates external_id from date+title+amount, so both
        # identical rows produce the same external_id — second is a duplicate.
        assert data["duplicateEntries"] >= 1


class TestConfirmBankImportMutation:
    def _preview_and_get_entries(
        self, client: FlaskClient, token: str, *, content: str, bank_name: str
    ) -> list[dict]:
        body = _gql(
            client,
            _PREVIEW_BANK_STATEMENT,
            {"content": content, "bankName": bank_name},
            token,
        )
        assert "errors" not in body, body.get("errors")
        return body["data"]["previewBankStatement"]["data"]["entries"]

    def test_confirm_imports_transactions(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "bs-confirm")
        entries = self._preview_and_get_entries(
            client, token, content=OFX_ITAU, bank_name="itau"
        )
        non_dup = [e for e in entries if not e["isDuplicate"]]
        assert non_dup, "Expected at least one non-duplicate entry to confirm"

        selected = [
            {
                "externalId": e["externalId"],
                "date": e["date"],
                "description": e["description"],
                "amount": e["amount"],
                "transactionType": e["transactionType"],
                "bankName": e["bankName"],
            }
            for e in non_dup
        ]

        body = _gql(
            client,
            _CONFIRM_BANK_IMPORT,
            {
                "bankName": "itau",
                "month": "2026-03",
                "mode": "selective",
                "selectedEntries": selected,
            },
            token,
        )
        assert "errors" not in body, body.get("errors")
        payload = body["data"]["confirmBankImport"]
        assert payload["ok"] is True
        assert payload["importedCount"] == len(non_dup)
        assert payload["bankName"] == "itau"
        assert payload["month"] == "2026-03"
        assert len(payload["transactions"]) == len(non_dup)

    def test_confirm_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(
            client,
            _CONFIRM_BANK_IMPORT,
            {
                "bankName": "itau",
                "month": "2026-03",
                "mode": "selective",
                "selectedEntries": [],
            },
        )
        assert "errors" in body
        code = (
            body["errors"][0].get("extensions", {}).get("code")
            or body["errors"][0]["message"]
        )
        assert (
            "UNAUTHORIZED" in str(code).upper()
            or "GRAPHQL_AUTH_REQUIRED" in str(code).upper()
        )

    def test_confirm_invalid_bank_returns_validation_error(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "bs-confirm-inv-bank")
        body = _gql(
            client,
            _CONFIRM_BANK_IMPORT,
            {
                "bankName": "badbank",
                "month": "2026-03",
                "mode": "selective",
                "selectedEntries": [
                    {
                        "externalId": "X1",
                        "date": "2026-03-01",
                        "description": "Test",
                        "amount": "10.00",
                        "transactionType": "expense",
                        "bankName": "badbank",
                    }
                ],
            },
            token,
        )
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_confirm_empty_entries_returns_validation_error(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "bs-confirm-empty")
        body = _gql(
            client,
            _CONFIRM_BANK_IMPORT,
            {
                "bankName": "nubank",
                "month": "2026-03",
                "mode": "selective",
                "selectedEntries": [],
            },
            token,
        )
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_confirm_invalid_month_format_returns_validation_error(
        self, client: FlaskClient
    ) -> None:
        token = _register_and_login(client, "bs-confirm-bad-month")
        body = _gql(
            client,
            _CONFIRM_BANK_IMPORT,
            {
                "bankName": "nubank",
                "month": "03-2026",  # wrong format
                "mode": "selective",
                "selectedEntries": [
                    {
                        "externalId": "X1",
                        "date": "2026-03-14",
                        "description": "Supermercado",
                        "amount": "-123.45",
                        "transactionType": "expense",
                        "bankName": "nubank",
                    }
                ],
            },
            token,
        )
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"
