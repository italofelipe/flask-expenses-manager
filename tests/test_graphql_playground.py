"""Tests for GET /graphql/playground endpoint."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch


def _login(client: Any, *, prefix: str = "playground-tester") -> str:
    import uuid

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
    return str(r2.get_json()["token"])


class TestGraphQLPlayground:
    def test_returns_404_when_flag_disabled(self, client: Any) -> None:
        with patch(
            "app.controllers.graphql.playground.is_feature_enabled", return_value=False
        ):
            response = client.get("/graphql/playground")
        assert response.status_code == 404

    def test_returns_403_when_not_authenticated(self, client: Any) -> None:
        with patch(
            "app.controllers.graphql.playground.is_feature_enabled", return_value=True
        ):
            response = client.get("/graphql/playground")
        assert response.status_code == 403

    def test_returns_403_when_not_admin(self, client: Any) -> None:
        token = _login(client)
        with patch(
            "app.controllers.graphql.playground.is_feature_enabled", return_value=True
        ):
            with patch(
                "app.controllers.graphql.playground._is_admin", return_value=False
            ):
                response = client.get(
                    "/graphql/playground",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert response.status_code == 403

    def test_returns_html_when_admin_and_flag_enabled(self, client: Any) -> None:
        token = _login(client)
        with patch(
            "app.controllers.graphql.playground.is_feature_enabled", return_value=True
        ):
            with patch(
                "app.controllers.graphql.playground._is_admin", return_value=True
            ):
                response = client.get(
                    "/graphql/playground",
                    headers={"Authorization": f"Bearer {token}"},
                )
        assert response.status_code == 200
        assert response.content_type.startswith("text/html")
        data = response.data.decode()
        assert "graphiql" in data.lower()
        assert "/graphql" in data

    def test_playground_html_contains_expected_elements(self, client: Any) -> None:
        token = _login(client)
        with patch(
            "app.controllers.graphql.playground.is_feature_enabled", return_value=True
        ):
            with patch(
                "app.controllers.graphql.playground._is_admin", return_value=True
            ):
                response = client.get(
                    "/graphql/playground",
                    headers={"Authorization": f"Bearer {token}"},
                )
        html = response.data.decode()
        assert "ReactDOM" in html or "graphiql" in html.lower()
        assert "fetchURL" in html or "url" in html.lower() or "/graphql" in html
