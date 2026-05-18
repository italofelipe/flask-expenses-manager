"""GraphQL parity tests for generateAiInsight mutation (MVP-3)."""

from __future__ import annotations

from unittest.mock import patch
from uuid import UUID, uuid4


def _register_and_login(client, *, prefix: str) -> str:
    suffix = uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    register = client.post(
        "/auth/register",
        json={"name": f"user-{suffix}", "email": email, "password": password},
    )
    assert register.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _gql(client, query, token=None, variables=None):
    headers = {"Content-Type": "application/json", "X-API-Contract": "v2"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


_GENERATE_MUTATION = """
mutation Gen($periodType: String!, $anchorDate: String) {
  generateAiInsight(periodType: $periodType, anchorDate: $anchorDate) {
    ok
    periodType
    summary
    items { type dimension title message evidence }
    cached
    model
  }
}
"""


class TestGenerateAiInsightMutation:
    def test_rejects_invalid_period_type(self, client):
        token = _register_and_login(client, prefix="gql-gen-invalid")
        response = _gql(
            client,
            _GENERATE_MUTATION,
            token,
            variables={"periodType": "yearly", "anchorDate": None},
        )
        body = response.get_json()
        assert body.get("errors")
        assert any("period_type" in e.get("message", "") for e in body["errors"])

    def test_rejects_invalid_anchor_date(self, client):
        token = _register_and_login(client, prefix="gql-gen-bad-date")
        response = _gql(
            client,
            _GENERATE_MUTATION,
            token,
            variables={"periodType": "daily", "anchorDate": "17/05/2026"},
        )
        body = response.get_json()
        assert body.get("errors")
        assert any("anchor_date" in e.get("message", "") for e in body["errors"])

    def test_requires_auth(self, client):
        response = _gql(client, _GENERATE_MUTATION, variables={"periodType": "daily"})
        body = response.get_json()
        assert response.status_code == 401 or body.get("errors")

    def test_returns_items_with_dimension_when_provider_returns_payload(
        self, app, client
    ):
        token = _register_and_login(client, prefix="gql-gen-ok")
        # Grant entitlement so the service does not block on Premium gate.
        from flask_jwt_extended import decode_token

        from app.services.entitlement_service import grant_entitlement

        with app.app_context():
            user_id = UUID(decode_token(token)["sub"])
            grant_entitlement(
                user_id=user_id,
                feature_key="advanced_simulations",
                source="trial",
            )
            from app.extensions.database import db

            db.session.commit()

        fake_result = {
            "period_type": "daily",
            "period_label": "2026-05-18",
            "period_start": "2026-05-18",
            "period_end": "2026-05-18",
            "summary": "Resumo do dia.",
            "items": [
                {
                    "type": "saude_financeira",
                    "dimension": "credit_cards",
                    "title": "Cartão Nubank no limite",
                    "message": "Você usou 80% do limite.",
                    "evidence": ["credit_cards[0].utilization_pct"],
                }
            ],
            "context_version": "financial_insight_snapshot.v1",
            "context_hash": "abc",
            "cached": False,
            "model": "gpt-4o-mini",
            "tokens_used": 50,
            "cost_usd": 0.0001,
        }
        with patch("app.graphql.mutations.ai_insight.AIAdvisoryService") as MockSvc:
            instance = MockSvc.return_value
            instance.generate_financial_insights.return_value = fake_result
            response = _gql(
                client,
                _GENERATE_MUTATION,
                token,
                variables={"periodType": "daily", "anchorDate": "2026-05-18"},
            )
        body = response.get_json()
        assert "errors" not in body or not body["errors"], body
        data = body["data"]["generateAiInsight"]
        assert data["ok"] is True
        assert data["summary"] == "Resumo do dia."
        assert len(data["items"]) == 1
        assert data["items"][0]["dimension"] == "credit_cards"
        assert data["items"][0]["evidence"] == ["credit_cards[0].utilization_pct"]
