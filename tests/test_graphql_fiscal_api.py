"""GraphQL tests for the Fiscal domain (#1247).

Covers: receivables query, receivablesSummary, fiscalDocuments,
        createReceivable mutation, markReceivableReceived, cancelReceivable,
        createFiscalDocument, and auth-required enforcement.
"""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient


def _register_and_login(client: FlaskClient, prefix: str = "fiscal") -> str:
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
# Query strings
# ---------------------------------------------------------------------------

_RECEIVABLES_QUERY = """
query Receivables($status: String) {
  receivables(status: $status) {
    total
    receivables {
      id
      fiscalDocumentId
      reconciliationStatus
      expectedNetAmount
      disclaimer
    }
  }
}
"""

_RECEIVABLES_SUMMARY = """
{
  receivablesSummary {
    expectedTotal
    receivedTotal
    pendingTotal
    disclaimer
  }
}
"""

_FISCAL_DOCS_QUERY = """
query FiscalDocs($type: String) {
  fiscalDocuments(type: $type) {
    total
    fiscalDocuments {
      id
      type
      status
      counterparty
      grossAmount
      currency
    }
  }
}
"""

_CREATE_RECEIVABLE = """
mutation CreateReceivable(
  $description: String!
  $amount: String!
  $expectedDate: String!
  $category: String
) {
  createReceivable(
    description: $description
    amount: $amount
    expectedDate: $expectedDate
    category: $category
  ) {
    ok
    message
    errors { field message }
    data {
      id
      reconciliationStatus
      expectedNetAmount
      disclaimer
    }
  }
}
"""

_MARK_RECEIVED = """
mutation MarkReceived(
  $entryId: UUID!
  $receivedDate: String!
  $receivedAmount: String
) {
  markReceivableReceived(
    entryId: $entryId
    receivedDate: $receivedDate
    receivedAmount: $receivedAmount
  ) {
    ok
    message
    data { id reconciliationStatus receivedAmount }
  }
}
"""

_CANCEL_RECEIVABLE = """
mutation CancelReceivable($entryId: UUID!) {
  cancelReceivable(entryId: $entryId) {
    ok
    message
    data { id reconciliationStatus }
  }
}
"""

_CREATE_FISCAL_DOC = """
mutation CreateFiscalDoc(
  $type: String!
  $amount: String!
  $issuedAt: String!
  $counterpartName: String
) {
  createFiscalDocument(
    type: $type
    amount: $amount
    issuedAt: $issuedAt
    counterpartName: $counterpartName
  ) {
    ok
    message
    errors { field message }
    data { id type status counterparty grossAmount }
  }
}
"""


# ---------------------------------------------------------------------------
# Tests — Receivables queries
# ---------------------------------------------------------------------------


class TestReceivablesQuery:
    def test_empty_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recvq")
        body = _gql(client, _RECEIVABLES_QUERY, token=token)
        assert "errors" not in body
        data = body["data"]["receivables"]
        assert data["total"] == 0
        assert data["receivables"] == []

    def test_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(client, _RECEIVABLES_QUERY)
        assert body["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"

    def test_summary_disclaimer_present(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recvs")
        body = _gql(client, _RECEIVABLES_SUMMARY, token=token)
        assert "errors" not in body
        summary = body["data"]["receivablesSummary"]
        assert "estimativo" in summary["disclaimer"]
        assert summary["expectedTotal"] == "0"
        assert summary["pendingTotal"] == "0"

    def test_summary_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(client, _RECEIVABLES_SUMMARY)
        assert body["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Tests — Fiscal documents query
# ---------------------------------------------------------------------------


class TestFiscalDocumentsQuery:
    def test_empty_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "fdocq")
        body = _gql(client, _FISCAL_DOCS_QUERY, token=token)
        assert "errors" not in body
        data = body["data"]["fiscalDocuments"]
        assert data["total"] == 0
        assert data["fiscalDocuments"] == []

    def test_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(client, _FISCAL_DOCS_QUERY)
        assert body["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Tests — createReceivable mutation
# ---------------------------------------------------------------------------


class TestCreateReceivableMutation:
    def test_create_success(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-create")
        body = _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "Consultoria Q1",
                "amount": "5000.00",
                "expectedDate": "2026-06-30",
                "category": "consulting",
            },
            token=token,
        )
        assert "errors" not in body
        result = body["data"]["createReceivable"]
        assert result["ok"] is True
        assert result["errors"] == []
        entry = result["data"]
        assert entry["id"]
        assert entry["reconciliationStatus"] == "pending"
        assert entry["expectedNetAmount"] == "5000.00"
        assert "estimativo" in entry["disclaimer"]

    def test_create_appears_in_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-list")
        _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "Projeto Alpha",
                "amount": "1000.00",
                "expectedDate": "2026-07-15",
            },
            token=token,
        )
        body = _gql(client, _RECEIVABLES_QUERY, token=token)
        assert body["data"]["receivables"]["total"] == 1

    def test_invalid_amount(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-badamt")
        body = _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "Test",
                "amount": "not-a-number",
                "expectedDate": "2026-06-01",
            },
            token=token,
        )
        assert body["errors"]

    def test_invalid_date(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-baddate")
        body = _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "Test",
                "amount": "100.00",
                "expectedDate": "not-a-date",
            },
            token=token,
        )
        assert body["errors"]

    def test_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "X",
                "amount": "1.00",
                "expectedDate": "2026-01-01",
            },
        )
        assert body["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"


# ---------------------------------------------------------------------------
# Tests — markReceivableReceived + cancelReceivable
# ---------------------------------------------------------------------------


class TestReceivableLifecycle:
    def _create_receivable(self, client: FlaskClient, token: str) -> str:
        body = _gql(
            client,
            _CREATE_RECEIVABLE,
            variables={
                "description": "Lifecycle test",
                "amount": "2500.00",
                "expectedDate": "2026-08-01",
            },
            token=token,
        )
        return body["data"]["createReceivable"]["data"]["id"]

    def test_mark_received(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-mark")
        entry_id = self._create_receivable(client, token)
        body = _gql(
            client,
            _MARK_RECEIVED,
            variables={
                "entryId": entry_id,
                "receivedDate": "2026-08-05",
                "receivedAmount": "2500.00",
            },
            token=token,
        )
        assert "errors" not in body
        result = body["data"]["markReceivableReceived"]
        assert result["ok"] is True
        assert result["data"]["receivedAmount"] == "2500.00"

    def test_cancel_receivable(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-cancel")
        entry_id = self._create_receivable(client, token)
        body = _gql(
            client,
            _CANCEL_RECEIVABLE,
            variables={"entryId": entry_id},
            token=token,
        )
        assert "errors" not in body
        result = body["data"]["cancelReceivable"]
        assert result["ok"] is True

    def test_not_found(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "recv-nf")
        fake_id = str(uuid.uuid4())
        body = _gql(
            client,
            _MARK_RECEIVED,
            variables={"entryId": fake_id, "receivedDate": "2026-01-01"},
            token=token,
        )
        assert body["errors"]
        assert body["errors"][0]["extensions"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Tests — createFiscalDocument mutation
# ---------------------------------------------------------------------------


class TestCreateFiscalDocumentMutation:
    def test_create_success(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "fdoc-create")
        body = _gql(
            client,
            _CREATE_FISCAL_DOC,
            variables={
                "type": "service_invoice",
                "amount": "3000.00",
                "issuedAt": "2026-05-01",
                "counterpartName": "Acme Corp",
            },
            token=token,
        )
        assert "errors" not in body
        result = body["data"]["createFiscalDocument"]
        assert result["ok"] is True
        doc = result["data"]
        assert doc["type"] == "service_invoice"
        assert doc["counterparty"] == "Acme Corp"
        assert doc["grossAmount"] == "3000.00"

    def test_invalid_type(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "fdoc-badtype")
        body = _gql(
            client,
            _CREATE_FISCAL_DOC,
            variables={
                "type": "not_a_valid_type",
                "amount": "100.00",
                "issuedAt": "2026-01-01",
            },
            token=token,
        )
        assert body["errors"]

    def test_appears_in_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "fdoc-list")
        _gql(
            client,
            _CREATE_FISCAL_DOC,
            variables={
                "type": "receipt",
                "amount": "500.00",
                "issuedAt": "2026-04-10",
            },
            token=token,
        )
        body = _gql(client, _FISCAL_DOCS_QUERY, token=token)
        assert body["data"]["fiscalDocuments"]["total"] == 1

    def test_requires_auth(self, client: FlaskClient) -> None:
        body = _gql(
            client,
            _CREATE_FISCAL_DOC,
            variables={"type": "receipt", "amount": "1.00", "issuedAt": "2026-01-01"},
        )
        assert body["errors"][0]["extensions"]["code"] == "UNAUTHORIZED"
