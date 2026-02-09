import uuid
from datetime import date, timedelta
from typing import Dict


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
