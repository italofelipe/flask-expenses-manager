"""Integration tests for GraphQL aiInsightHistory query (#1231).

Coverage:
- Happy path: authenticated user retrieves their insights
- Unauthenticated request is rejected with HTTP 401
- User isolation: each user only sees their own insights
- Pagination: page and perPage parameters work correctly
- Empty state: returns empty items list with total=0
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from typing import Any

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GQL_AI_INSIGHT_HISTORY = """
query AiInsightHistory($page: Int, $perPage: Int) {
  aiInsightHistory(page: $page, perPage: $perPage) {
    items {
      id
      content
      insightType
      periodLabel
      periodStart
      periodEnd
      model
      tokensUsed
      costUsd
      createdAt
    }
    page
    perPage
    total
  }
}
"""


def _graphql(
    client,
    query: str,
    variables: dict[str, Any] | None = None,
    token: str | None = None,
) -> Any:
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return client.post(
        "/graphql",
        json={"query": query, "variables": variables or {}},
        headers=headers,
    )


def _register_and_login(client, prefix: str = "gql-ai") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    reg = client.post(
        "/auth/register",
        json={
            "name": f"{prefix}-{suffix}",
            "email": email,
            "password": "StrongPass@123",
        },
    )
    assert reg.status_code == 201
    login = client.post(
        "/auth/login", json={"email": email, "password": "StrongPass@123"}
    )
    assert login.status_code == 200
    return login.get_json()["token"]


def _get_user_id(app, token: str) -> uuid.UUID:
    with app.app_context():
        from flask_jwt_extended import decode_token

        return uuid.UUID(decode_token(token)["sub"])


def _create_insight(
    app,
    user_id: uuid.UUID,
    *,
    content: str = "Test insight",
    insight_type: InsightType = InsightType.daily,
    period_label: str = "2026-05-12",
    period_start: date | None = None,
    period_end: date | None = None,
    model: str = "gpt-4o-mini",
    tokens_used: int = 100,
    cost_usd: float = 0.000015,
) -> AIInsight:
    with app.app_context():
        today = date(2026, 5, 12)
        insight = AIInsight(
            user_id=user_id,
            content=content,
            insight_type=insight_type,
            period_label=period_label,
            period_start=period_start or today,
            period_end=period_end or today,
            model=model,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
            created_at=datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc).replace(
                tzinfo=None
            ),
        )
        db.session.add(insight)
        db.session.commit()
        return insight


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAiInsightHistoryQuery:
    def test_happy_path_returns_insight(self, client, app):
        token = _register_and_login(client)
        user_id = _get_user_id(app, token)
        _create_insight(app, user_id, content="Daily spending insight")

        resp = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token)

        assert resp.status_code == 200
        body = resp.get_json()
        assert "errors" not in body
        result = body["data"]["aiInsightHistory"]
        assert result["total"] == 1
        assert result["page"] == 1
        assert result["perPage"] == 20
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["content"] == "Daily spending insight"
        assert item["insightType"] == "daily"
        assert item["periodLabel"] == "2026-05-12"
        assert item["periodStart"] == "2026-05-12"
        assert item["model"] == "gpt-4o-mini"
        assert item["tokensUsed"] == 100
        assert isinstance(item["costUsd"], float)
        assert item["id"] is not None
        assert item["createdAt"] is not None

    def test_auth_required_without_token(self, client):
        resp = _graphql(client, _GQL_AI_INSIGHT_HISTORY)

        # The GraphQL auth middleware intercepts unauthenticated requests before
        # the resolver runs and returns HTTP 401 directly.
        assert resp.status_code == 401

    def test_user_isolation(self, client, app):
        token_a = _register_and_login(client, "user-a")
        token_b = _register_and_login(client, "user-b")
        user_id_a = _get_user_id(app, token_a)
        user_id_b = _get_user_id(app, token_b)

        _create_insight(app, user_id_a, content="User A insight")
        _create_insight(app, user_id_b, content="User B insight")

        resp_a = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token_a)
        body_a = resp_a.get_json()
        assert "errors" not in body_a
        result_a = body_a["data"]["aiInsightHistory"]
        assert result_a["total"] == 1
        contents_a = [i["content"] for i in result_a["items"]]
        assert "User A insight" in contents_a
        assert "User B insight" not in contents_a

        resp_b = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token_b)
        body_b = resp_b.get_json()
        result_b = body_b["data"]["aiInsightHistory"]
        assert result_b["total"] == 1
        contents_b = [i["content"] for i in result_b["items"]]
        assert "User B insight" in contents_b
        assert "User A insight" not in contents_b

    def test_pagination(self, client, app):
        token = _register_and_login(client)
        user_id = _get_user_id(app, token)

        for i in range(5):
            _create_insight(
                app,
                user_id,
                content=f"Insight {i}",
                period_label=f"2026-05-{12 - i:02d}",
                period_start=date(2026, 5, 12 - i),
                period_end=date(2026, 5, 12 - i),
            )

        resp = _graphql(
            client,
            _GQL_AI_INSIGHT_HISTORY,
            variables={"page": 1, "perPage": 2},
            token=token,
        )
        body = resp.get_json()
        assert "errors" not in body
        result = body["data"]["aiInsightHistory"]
        assert result["total"] == 5
        assert result["page"] == 1
        assert result["perPage"] == 2
        assert len(result["items"]) == 2

        resp2 = _graphql(
            client,
            _GQL_AI_INSIGHT_HISTORY,
            variables={"page": 3, "perPage": 2},
            token=token,
        )
        body2 = resp2.get_json()
        result2 = body2["data"]["aiInsightHistory"]
        assert result2["total"] == 5
        assert result2["page"] == 3
        assert len(result2["items"]) == 1

    def test_empty_history(self, client):
        token = _register_and_login(client)

        resp = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token)

        assert resp.status_code == 200
        body = resp.get_json()
        assert "errors" not in body
        result = body["data"]["aiInsightHistory"]
        assert result["total"] == 0
        assert result["items"] == []
        assert result["page"] == 1

    def test_default_pagination_values(self, client, app):
        token = _register_and_login(client)
        user_id = _get_user_id(app, token)
        _create_insight(app, user_id)

        resp = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token)

        body = resp.get_json()
        result = body["data"]["aiInsightHistory"]
        assert result["page"] == 1
        assert result["perPage"] == 20

    def test_multiple_insight_types(self, client, app):
        token = _register_and_login(client)
        user_id = _get_user_id(app, token)

        _create_insight(
            app,
            user_id,
            insight_type=InsightType.daily,
            period_label="2026-05-12",
        )
        _create_insight(
            app,
            user_id,
            insight_type=InsightType.weekly,
            period_label="2026-W20",
        )
        _create_insight(
            app,
            user_id,
            insight_type=InsightType.monthly,
            period_label="2026-05",
        )

        resp = _graphql(client, _GQL_AI_INSIGHT_HISTORY, token=token)
        body = resp.get_json()
        result = body["data"]["aiInsightHistory"]
        assert result["total"] == 3
        types_returned = {i["insightType"] for i in result["items"]}
        assert types_returned == {"daily", "weekly", "monthly"}
