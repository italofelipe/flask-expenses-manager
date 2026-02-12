import uuid
from datetime import date
from uuid import UUID

from app.extensions.database import db
from app.models.account import Account
from app.models.tag import Tag
from app.models.transaction import Transaction


def _register_and_login(client, prefix: str) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    body = login_response.get_json()
    return str(body["token"]), str(body["user"]["id"])


def _auth_headers(token: str, contract: str | None = "v2") -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract is not None:
        headers["X-API-Contract"] = contract
    return headers


def _transaction_payload(**overrides: str) -> dict[str, str]:
    payload = {
        "title": "Conta de água",
        "amount": "120.50",
        "type": "expense",
        "due_date": date.today().isoformat(),
    }
    payload.update(overrides)
    return payload


def test_transaction_create_rejects_foreign_tag_reference(client) -> None:
    owner_token, _ = _register_and_login(client, "tx-owner-tag")
    _, other_user_id = _register_and_login(client, "tx-other-tag")

    with client.application.app_context():
        foreign_tag = Tag(user_id=UUID(other_user_id), name="foreign")
        db.session.add(foreign_tag)
        db.session.commit()
        foreign_tag_id = str(foreign_tag.id)

    response = client.post(
        "/transactions",
        headers=_auth_headers(owner_token),
        json=_transaction_payload(tag_id=foreign_tag_id),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Referência inválida" in body["message"]


def test_transaction_update_rejects_foreign_account_reference(client) -> None:
    owner_token, _ = _register_and_login(client, "tx-owner-account")
    _, other_user_id = _register_and_login(client, "tx-other-account")

    created = client.post(
        "/transactions",
        headers=_auth_headers(owner_token),
        json=_transaction_payload(),
    )
    assert created.status_code == 201
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]

    with client.application.app_context():
        foreign_account = Account(user_id=UUID(other_user_id), name="foreign-account")
        db.session.add(foreign_account)
        db.session.commit()
        foreign_account_id = str(foreign_account.id)

    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(owner_token),
        json={"account_id": foreign_account_id},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert "Referência inválida" in body["message"]


def test_transaction_update_rejects_user_id_payload_mutation(client) -> None:
    owner_token, owner_user_id = _register_and_login(client, "tx-owner-userid")
    _, other_user_id = _register_and_login(client, "tx-other-userid")

    created = client.post(
        "/transactions",
        headers=_auth_headers(owner_token),
        json=_transaction_payload(),
    )
    assert created.status_code == 201
    transaction_id = created.get_json()["data"]["transaction"][0]["id"]
    response = client.put(
        f"/transactions/{transaction_id}",
        headers=_auth_headers(owner_token),
        json={"title": "Titulo nao aplicado", "user_id": other_user_id},
    )
    assert response.status_code == 400
    response_body = response.get_json()
    assert response_body["error"]["code"] == "VALIDATION_ERROR"
    assert "user_id" in str(response_body["error"]["details"])

    with client.application.app_context():
        transaction = db.session.get(Transaction, UUID(transaction_id))
        assert transaction is not None
        assert str(transaction.user_id) == owner_user_id
        assert transaction.title != "Titulo nao aplicado"


def test_transaction_internal_error_response_does_not_expose_exception(
    client, monkeypatch
):
    token, _ = _register_and_login(client, "tx-internal-error")

    original_commit = db.session.commit

    def _raise_commit_error() -> None:
        raise RuntimeError("sensitive-db-error")

    monkeypatch.setattr(db.session, "commit", _raise_commit_error)

    response = client.post(
        "/transactions",
        headers=_auth_headers(token),
        json=_transaction_payload(),
    )

    monkeypatch.setattr(db.session, "commit", original_commit)

    assert response.status_code == 500
    body = response.get_json()
    serialized = str(body)
    assert body["error"]["code"] == "INTERNAL_ERROR"
    assert "sensitive-db-error" not in serialized
