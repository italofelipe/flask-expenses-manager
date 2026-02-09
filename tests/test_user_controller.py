import uuid
from datetime import date, timedelta
from decimal import Decimal
from uuid import UUID

from flask import Response
from sqlalchemy.orm.query import Query

from app.controllers.user_controller import (
    assign_user_profile_fields,
    filter_transactions,
    validate_user_token,
)
from app.extensions.database import db
from app.models.user import User
from app.models.wallet import Wallet


def _register_and_login(client) -> tuple[str, str]:
    suffix = uuid.uuid4().hex[:8]
    email = f"user-{suffix}@email.com"
    password = "StrongPass@123"

    register_response = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert register_response.status_code == 201

    login_response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert login_response.status_code == 200
    return login_response.get_json()["token"], email


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_assign_user_profile_fields_invalid_date_format() -> None:
    user = User(name="n", email="u@test.com", password="hash")
    result = assign_user_profile_fields(user, {"birth_date": "2026/02/09"})

    assert result["error"] is True
    assert "Formato inválido" in str(result["message"])


def test_assign_user_profile_fields_success_with_valid_date() -> None:
    user = User(name="n", email="u2@test.com", password="hash")
    result = assign_user_profile_fields(user, {"birth_date": "2020-01-01"})

    assert result["error"] is False
    assert str(user.birth_date) == "2020-01-01"


def test_validate_user_token_invalid_returns_401_response(app) -> None:
    with app.app_context():
        response = validate_user_token(UUID(uuid.uuid4().hex), "jti")
        assert isinstance(response, Response)
        assert response.status_code == 401


def test_filter_transactions_invalid_status_returns_400(app) -> None:
    with app.app_context():
        response = filter_transactions(UUID(uuid.uuid4().hex), "invalid-status", "")
        assert isinstance(response, Response)
        assert response.status_code == 400


def test_filter_transactions_invalid_month_returns_400(app) -> None:
    with app.app_context():
        response = filter_transactions(UUID(uuid.uuid4().hex), "", "2026-XX")
        assert isinstance(response, Response)
        assert response.status_code == 400


def test_filter_transactions_valid_returns_query(app) -> None:
    with app.app_context():
        query = filter_transactions(UUID(uuid.uuid4().hex), "", "")
        assert isinstance(query, Query)


def test_user_profile_update_success(client) -> None:
    token, _ = _register_and_login(client)
    response = client.put(
        "/user/profile",
        headers=_auth_headers(token),
        json={
            "gender": "masculino",
            "monthly_income": "5000.00",
            "investment_goal_date": (date.today() + timedelta(days=30)).isoformat(),
        },
    )

    assert response.status_code == 200
    body = response.get_json()
    assert body["message"] == "Perfil atualizado com sucesso"
    assert body["data"]["gender"] == "masculino"


def test_user_profile_update_validation_error(client) -> None:
    token, _ = _register_and_login(client)
    response = client.put(
        "/user/profile",
        headers=_auth_headers(token),
        json={"monthly_income": "-1.00"},
    )

    assert response.status_code == 400
    assert "message" in response.get_json()


def test_user_me_success_with_wallet_and_transaction(client, app) -> None:
    token, email = _register_and_login(client)
    create_transaction = client.post(
        "/transactions",
        headers=_auth_headers(token),
        json={
            "title": "Receita",
            "amount": "100.00",
            "type": "income",
            "due_date": date.today().isoformat(),
        },
    )
    assert create_transaction.status_code == 201

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        wallet = Wallet(
            user_id=user.id,
            name="Caixa",
            value=Decimal("1000.00"),
            estimated_value_on_create_date=Decimal("1000.00"),
            quantity=1,
            should_be_on_wallet=True,
            register_date=date.today(),
        )
        db.session.add(wallet)
        db.session.commit()

    response = client.get("/user/me?page=1&limit=10", headers=_auth_headers(token))

    assert response.status_code == 200
    body = response.get_json()
    assert "user" in body
    assert "transactions" in body
    assert "wallet" in body
    assert len(body["wallet"]) >= 1


def test_user_me_invalid_status_returns_400(client) -> None:
    token, _ = _register_and_login(client)
    response = client.get(
        "/user/me?status=invalid-status",
        headers=_auth_headers(token),
    )

    assert response.status_code == 400
    assert "Status inválido" in response.get_json()["message"]


def test_user_me_invalid_month_returns_400(client) -> None:
    token, _ = _register_and_login(client)
    response = client.get(
        "/user/me?month=2026-XX",
        headers=_auth_headers(token),
    )

    assert response.status_code == 400
    assert "Parâmetro 'month' inválido" in response.get_json()["message"]


def test_user_me_with_revoked_jti_returns_401(client, app) -> None:
    token, email = _register_and_login(client)

    with app.app_context():
        user = User.query.filter_by(email=email).first()
        assert user is not None
        user.current_jti = "manually-revoked"
        db.session.commit()

    response = client.get("/user/me", headers=_auth_headers(token))

    assert response.status_code == 401
    assert response.get_json()["message"] in (
        "Token revogado",
        "Token inválido ou ausente",
    )
