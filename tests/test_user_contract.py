import uuid
from datetime import date, timedelta
from decimal import Decimal
from typing import Dict

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.wallet import Wallet


def _register_and_login(client) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"user-contract-{suffix}@email.com"
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


def _auth_headers(token: str, contract: str | None = None) -> Dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if contract:
        headers["X-API-Contract"] = contract
    return headers


USER_FIELDS = {
    "id",
    "name",
    "email",
    "gender",
    "birth_date",
    "monthly_income",
    "monthly_income_net",
    "net_worth",
    "monthly_expenses",
    "initial_investment",
    "monthly_investment",
    "investment_goal_date",
    "state_uf",
    "occupation",
    "investor_profile",
    "financial_objectives",
    "investor_profile_suggested",
    "profile_quiz_score",
    "taxonomy_version",
}

TRANSACTION_ITEM_FIELDS = {
    "id",
    "title",
    "amount",
    "type",
    "due_date",
    "status",
    "description",
    "observation",
    "is_recurring",
    "is_installment",
    "installment_count",
    "tag_id",
    "account_id",
    "credit_card_id",
    "currency",
    "created_at",
    "updated_at",
}

WALLET_ITEM_FIELDS = {
    "id",
    "name",
    "value",
    "estimated_value_on_create_date",
    "ticker",
    "quantity",
    "asset_class",
    "annual_rate",
    "target_withdraw_date",
    "register_date",
    "should_be_on_wallet",
}


def _seed_me_contract_entities(client, app) -> str:
    token = _register_and_login(client)
    auth_context = client.get(
        "/user/me",
        headers=_auth_headers(token),
    )
    assert auth_context.status_code == 200
    email = auth_context.get_json()["user"]["email"]

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None

        transaction_one = Transaction(
            user_id=user.id,
            title="Receita recorrente",
            amount=Decimal("100.00"),
            type=TransactionType.INCOME,
            due_date=date.today(),
            status=TransactionStatus.PAID,
            currency="BRL",
            deleted=False,
        )
        transaction_two = Transaction(
            user_id=user.id,
            title="Despesa mensal",
            amount=Decimal("45.50"),
            type=TransactionType.EXPENSE,
            due_date=date.today() + timedelta(days=1),
            status=TransactionStatus.PENDING,
            currency="BRL",
            deleted=False,
        )
        wallet_one = Wallet(
            user_id=user.id,
            name="Caixa",
            value=Decimal("1000.00"),
            estimated_value_on_create_date=Decimal("1000.00"),
            quantity=1,
            should_be_on_wallet=True,
            register_date=date.today(),
        )
        wallet_two = Wallet(
            user_id=user.id,
            name="Reserva",
            value=Decimal("2000.00"),
            estimated_value_on_create_date=Decimal("2000.00"),
            quantity=1,
            should_be_on_wallet=True,
            register_date=date.today(),
        )
        db.session.add_all([transaction_one, transaction_two, wallet_one, wallet_two])
        db.session.commit()

    return token


def test_user_profile_v1_legacy_contract(client) -> None:
    token = _register_and_login(client)
    response = client.put(
        "/user/profile",
        headers=_auth_headers(token),
        json={
            "gender": "masculino",
            "investment_goal_date": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert "success" not in body
    assert body["message"] == "Perfil atualizado com sucesso"
    assert "data" in body


def test_user_profile_v2_contract(client) -> None:
    token = _register_and_login(client)
    response = client.put(
        "/user/profile",
        headers=_auth_headers(token, "v2"),
        json={
            "gender": "outro",
            "investment_goal_date": (date.today() + timedelta(days=60)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert body["message"] == "Perfil atualizado com sucesso"
    assert "user" in body["data"]


def test_user_profile_validation_error_v2_contract(client) -> None:
    token = _register_and_login(client)
    response = client.put(
        "/user/profile",
        headers=_auth_headers(token, "v2"),
        json={"investment_goal_date": (date.today() - timedelta(days=1)).isoformat()},
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_user_me_v1_legacy_contract(client) -> None:
    token = _register_and_login(client)
    response = client.get("/user/me?page=1&limit=10", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.get_json()
    assert "success" not in body
    assert "user" in body
    assert "transactions" in body
    assert "wallet" in body


def test_user_me_v2_contract_has_meta_pagination(client) -> None:
    token = _register_and_login(client)
    response = client.get(
        "/user/me?page=1&limit=10",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["success"] is True
    assert "user" in body["data"]
    assert "transactions" in body["data"]
    assert "wallet" in body["data"]
    assert "pagination" in body["meta"]


def test_user_me_v2_contract_freezes_current_field_sets(client, app) -> None:
    token = _seed_me_contract_entities(client, app)

    response = client.get(
        "/user/me?page=1&limit=10",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()

    assert set(body["data"]["user"].keys()) == USER_FIELDS
    assert body["data"]["transactions"]["items"]
    assert body["data"]["wallet"]
    assert (
        set(body["data"]["transactions"]["items"][0].keys()) == TRANSACTION_ITEM_FIELDS
    )
    assert set(body["data"]["wallet"][0].keys()) == WALLET_ITEM_FIELDS


def test_user_me_legacy_pagination_only_applies_to_transactions(client, app) -> None:
    token = _seed_me_contract_entities(client, app)

    response = client.get(
        "/user/me?page=1&limit=1",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 200
    body = response.get_json()

    assert len(body["data"]["transactions"]["items"]) == 1
    assert body["data"]["transactions"]["total"] >= 2
    assert len(body["data"]["wallet"]) == 2


def test_user_me_invalid_status_v2_contract(client) -> None:
    token = _register_and_login(client)
    response = client.get(
        "/user/me?status=invalid",
        headers=_auth_headers(token, "v2"),
    )

    assert response.status_code == 400
    body = response.get_json()
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"


def test_user_me_masks_unexpected_value_error(client, monkeypatch) -> None:
    token = _register_and_login(client)

    def _raise_unexpected_value_error(*_args: object, **_kwargs: object) -> int:
        raise ValueError("sqlalchemy internal error leaked")

    monkeypatch.setattr(
        "app.controllers.user_controller._parse_positive_int",
        _raise_unexpected_value_error,
    )

    response = client.get(
        "/user/me?page=1&limit=10",
        headers=_auth_headers(token, "v2"),
    )
    assert response.status_code == 400
    body = response.get_json()
    serialized = str(body)
    assert body["success"] is False
    assert body["error"]["code"] == "VALIDATION_ERROR"
    assert body["message"] == "Parâmetros de paginação inválidos."
    assert "sqlalchemy internal error leaked" not in serialized
