from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.wallet import Wallet


def _register_and_login(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"user-bootstrap-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={
            "name": f"user-{suffix}",
            "email": email,
            "password": password,
        },
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.get_json()["token"]


def _auth_headers(token: str, contract: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


def _seed_bootstrap_entities(client, app) -> str:
    token = _register_and_login(client)
    me_response = client.get("/user/me", headers=_auth_headers(token))
    assert me_response.status_code == 200
    email = me_response.get_json()["user"]["email"]

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None

        transactions = [
            Transaction(
                user_id=user.id,
                title=f"Transaction {index}",
                amount=Decimal("10.00"),
                type=TransactionType.EXPENSE,
                due_date=date.today() + timedelta(days=index),
                status=TransactionStatus.PENDING,
                currency="BRL",
                deleted=False,
            )
            for index in range(3)
        ]
        wallet_entry = Wallet(
            user_id=user.id,
            name="Reserva",
            value=Decimal("1500.00"),
            estimated_value_on_create_date=Decimal("1500.00"),
            quantity=1,
            should_be_on_wallet=True,
            register_date=date.today(),
        )
        db.session.add_all([*transactions, wallet_entry])
        db.session.commit()

    return token


def test_user_bootstrap_v2_contract_returns_aggregated_payload(client, app) -> None:
    token = _seed_bootstrap_entities(client, app)

    response = client.get(
        "/user/bootstrap?transactions_limit=2",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Bootstrap do usuário retornado com sucesso"
    assert set(body["data"].keys()) == {"user", "transactions_preview", "wallet"}
    assert set(body["data"]["user"].keys()) == {
        "identity",
        "profile",
        "financial_profile",
        "investor_profile",
        "product_context",
    }
    assert body["data"]["transactions_preview"]["limit"] == 2
    assert body["data"]["transactions_preview"]["returned_items"] == 2
    assert body["data"]["transactions_preview"]["has_more"] is True
    assert len(body["data"]["transactions_preview"]["items"]) == 2
    assert body["data"]["wallet"]["total"] == 1
    assert len(body["data"]["wallet"]["items"]) == 1


def test_user_bootstrap_invalid_limit_returns_validation_error(client) -> None:
    token = _register_and_login(client)

    response = client.get(
        "/user/bootstrap?transactions_limit=999",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Parâmetros do bootstrap inválidos."
