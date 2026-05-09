"""GraphQL tests for Tags and Accounts domains (#1148)."""

from __future__ import annotations

import uuid

from flask.testing import FlaskClient


def _register_and_login(client: FlaskClient, prefix: str = "gql") -> str:
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
# Tags
# ---------------------------------------------------------------------------

_CREATE_TAG = """
mutation CreateTag($name: String!, $color: String, $icon: String) {
  createTag(name: $name, color: $color, icon: $icon) {
    ok message errors { field message }
    data { id name color icon }
  }
}
"""

_UPDATE_TAG = """
mutation UpdateTag($tagId: UUID!, $name: String!) {
  updateTag(tagId: $tagId, name: $name) {
    ok message data { id name }
  }
}
"""

_DELETE_TAG = """
mutation DeleteTag($tagId: UUID!) {
  deleteTag(tagId: $tagId) { ok message }
}
"""

_TAGS_QUERY = "{ tags { total tags { id name color icon } } }"
_TAG_QUERY = "query Tag($id: UUID!) { tag(tagId: $id) { id name } }"


class TestTagsGraphQL:
    def test_create_tag(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-create")
        body = _gql(
            client, _CREATE_TAG, {"name": "Alimentação", "color": "#FF6B6B"}, token
        )
        assert "errors" not in body
        payload = body["data"]["createTag"]
        assert payload["ok"] is True
        assert payload["data"]["name"] == "Alimentação"
        assert payload["data"]["color"] == "#FF6B6B"

    def test_tags_query_returns_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-list")
        _gql(client, _CREATE_TAG, {"name": "Transporte"}, token)
        body = _gql(client, _TAGS_QUERY, token=token)
        assert "errors" not in body
        assert body["data"]["tags"]["total"] >= 1
        names = [t["name"] for t in body["data"]["tags"]["tags"]]
        assert "Transporte" in names

    def test_update_tag(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-update")
        created = _gql(client, _CREATE_TAG, {"name": "Lazer"}, token)
        tag_id = created["data"]["createTag"]["data"]["id"]
        body = _gql(
            client, _UPDATE_TAG, {"tagId": tag_id, "name": "Entretenimento"}, token
        )
        assert body["data"]["updateTag"]["ok"] is True
        assert body["data"]["updateTag"]["data"]["name"] == "Entretenimento"

    def test_delete_tag(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-delete")
        created = _gql(client, _CREATE_TAG, {"name": "Temp"}, token)
        tag_id = created["data"]["createTag"]["data"]["id"]
        body = _gql(client, _DELETE_TAG, {"tagId": tag_id}, token)
        assert body["data"]["deleteTag"]["ok"] is True

    def test_create_tag_invalid_color(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-inv-color")
        body = _gql(client, _CREATE_TAG, {"name": "Foo", "color": "not-a-color"}, token)
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_tag_not_found_returns_null(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "tag-404")
        body = _gql(client, _TAG_QUERY, {"id": str(uuid.uuid4())}, token)
        assert "errors" not in body
        assert body["data"]["tag"] is None

    def test_tag_isolated_by_user(self, client: FlaskClient) -> None:
        token_a = _register_and_login(client, "tag-iso-a")
        token_b = _register_and_login(client, "tag-iso-b")
        created = _gql(client, _CREATE_TAG, {"name": "Private"}, token_a)
        tag_id = created["data"]["createTag"]["data"]["id"]
        body = _gql(client, _DELETE_TAG, {"tagId": tag_id}, token_b)
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "NOT_FOUND"

    def test_tags_require_auth(self, client: FlaskClient) -> None:
        body = _gql(client, _TAGS_QUERY)
        assert "errors" in body


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

_CREATE_ACCOUNT = """
mutation CreateAccount(
  $name: String!, $accountType: String,
  $institution: String, $initialBalance: String
) {
  createAccount(
    name: $name, accountType: $accountType,
    institution: $institution, initialBalance: $initialBalance
  ) {
    ok message errors { field message }
    data { id name accountType institution initialBalance }
  }
}
"""

_UPDATE_ACCOUNT = """
mutation UpdateAccount($accountId: UUID!, $name: String!) {
  updateAccount(accountId: $accountId, name: $name) {
    ok message data { id name accountType }
  }
}
"""

_DELETE_ACCOUNT = """
mutation DeleteAccount($accountId: UUID!) {
  deleteAccount(accountId: $accountId) { ok message }
}
"""

_ACCOUNTS_QUERY = "{ accounts { total accounts { id name accountType institution } } }"


class TestAccountsGraphQL:
    def test_create_account(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "acc-create")
        body = _gql(
            client,
            _CREATE_ACCOUNT,
            {
                "name": "Nubank",
                "accountType": "checking",
                "institution": "Nubank",
                "initialBalance": "1000.50",
            },
            token,
        )
        assert "errors" not in body
        payload = body["data"]["createAccount"]
        assert payload["ok"] is True
        assert payload["data"]["name"] == "Nubank"
        assert payload["data"]["accountType"] == "checking"

    def test_accounts_query_returns_list(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "acc-list")
        _gql(client, _CREATE_ACCOUNT, {"name": "Inter"}, token)
        body = _gql(client, _ACCOUNTS_QUERY, token=token)
        assert "errors" not in body
        assert body["data"]["accounts"]["total"] >= 1

    def test_update_account(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "acc-update")
        created = _gql(client, _CREATE_ACCOUNT, {"name": "Old Name"}, token)
        acc_id = created["data"]["createAccount"]["data"]["id"]
        body = _gql(
            client, _UPDATE_ACCOUNT, {"accountId": acc_id, "name": "New Name"}, token
        )
        assert body["data"]["updateAccount"]["ok"] is True
        assert body["data"]["updateAccount"]["data"]["name"] == "New Name"

    def test_delete_account(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "acc-delete")
        created = _gql(client, _CREATE_ACCOUNT, {"name": "Temp Account"}, token)
        acc_id = created["data"]["createAccount"]["data"]["id"]
        body = _gql(client, _DELETE_ACCOUNT, {"accountId": acc_id}, token)
        assert body["data"]["deleteAccount"]["ok"] is True

    def test_create_account_invalid_type(self, client: FlaskClient) -> None:
        token = _register_and_login(client, "acc-inv-type")
        body = _gql(
            client,
            _CREATE_ACCOUNT,
            {"name": "Test", "accountType": "invalid_type"},
            token,
        )
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "VALIDATION_ERROR"

    def test_account_isolated_by_user(self, client: FlaskClient) -> None:
        token_a = _register_and_login(client, "acc-iso-a")
        token_b = _register_and_login(client, "acc-iso-b")
        created = _gql(client, _CREATE_ACCOUNT, {"name": "Private Account"}, token_a)
        acc_id = created["data"]["createAccount"]["data"]["id"]
        body = _gql(client, _DELETE_ACCOUNT, {"accountId": acc_id}, token_b)
        assert "errors" in body
        assert body["errors"][0]["extensions"]["code"] == "NOT_FOUND"

    def test_accounts_require_auth(self, client: FlaskClient) -> None:
        body = _gql(client, _ACCOUNTS_QUERY)
        assert "errors" in body
