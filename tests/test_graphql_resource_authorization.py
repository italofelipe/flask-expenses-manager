from __future__ import annotations

from typing import Any, Callable
from uuid import UUID

import pytest

from app.extensions.database import db
from app.models.account import Account
from app.models.credit_card import CreditCard
from app.models.tag import Tag
from app.models.user import User


def _graphql(
    client: Any,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
):
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login(client: Any, suffix: str) -> str:
    register_mutation = """
    mutation Register($name: String!, $email: String!, $password: String!) {
      registerUser(name: $name, email: $email, password: $password) {
        message
      }
    }
    """
    email = f"{suffix}@email.com"
    response = _graphql(
        client,
        register_mutation,
        {"name": suffix, "email": email, "password": "StrongPass@123"},
    )
    assert response.status_code == 200
    assert "errors" not in response.get_json()

    login_mutation = """
    mutation Login($email: String!, $password: String!) {
      login(email: $email, password: $password) {
        token
      }
    }
    """
    login_response = _graphql(
        client,
        login_mutation,
        {"email": email, "password": "StrongPass@123"},
    )
    assert login_response.status_code == 200
    body = login_response.get_json()
    assert body and "errors" not in body
    return str(body["data"]["login"]["token"])


def _get_user_id_by_email(app: Any, email: str) -> UUID:
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        return UUID(str(user.id))


@pytest.mark.parametrize(
    ("resource_field", "factory"),
    [
        ("tagId", lambda user_id: Tag(user_id=user_id, name="other-tag")),
        ("accountId", lambda user_id: Account(user_id=user_id, name="other-account")),
        (
            "creditCardId",
            lambda user_id: CreditCard(user_id=user_id, name="other-card"),
        ),
    ],
)
def test_graphql_create_transaction_denies_foreign_reference_ids(
    app: Any,
    client: Any,
    resource_field: str,
    factory: Callable[[UUID], Any],
) -> None:
    owner_token = _register_and_login(client, "graphql-owner")
    _register_and_login(client, "graphql-other")

    owner_user_id = _get_user_id_by_email(app, "graphql-owner@email.com")
    other_user_id = _get_user_id_by_email(app, "graphql-other@email.com")
    assert owner_user_id != other_user_id

    with app.app_context():
        resource = factory(other_user_id)
        db.session.add(resource)
        db.session.commit()
        foreign_id = str(resource.id)

    mutation = f"""
    mutation CreateTx(
      $title: String!,
      $amount: String!,
      $type: String!,
      $dueDate: String!,
      ${resource_field}: UUID
    ) {{
      createTransaction(
        title: $title,
        amount: $amount,
        type: $type,
        dueDate: $dueDate,
        {resource_field}: ${resource_field}
      ) {{
        message
        items {{ id }}
      }}
    }}
    """
    variables = {
        "title": "Teste authz por recurso",
        "amount": "10.00",
        "type": "expense",
        "dueDate": "2026-02-11",
        resource_field: foreign_id,
    }
    response = _graphql(client, mutation, variables, token=owner_token)
    assert response.status_code in {200, 400}
    body = response.get_json()
    assert body is not None
    assert "errors" in body
    if "data" in body:
        assert body["data"]["createTransaction"] is None
    assert body["errors"][0]["message"].startswith("Referência inválida para")
