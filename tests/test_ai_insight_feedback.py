"""Tests for the AI insight feedback/rating loop (#1387)."""

from __future__ import annotations

import json
import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.ai_insight_feedback import AIInsightFeedback
from app.models.user import User


def _make_user() -> uuid.UUID:
    user = User(
        name="FB Tester",
        email=f"fb-{uuid.uuid4().hex[:8]}@email.com",
        password="hash",
    )
    db.session.add(user)
    db.session.commit()
    return user.id


def _make_insight(user_id: uuid.UUID) -> uuid.UUID:
    insight = AIInsight(
        user_id=user_id,
        content=json.dumps({"summary": "x", "items": []}),
        insight_type=InsightType.daily,
        period_label="2026-05-30",
        period_start=date(2026, 5, 30),
        period_end=date(2026, 5, 30),
        model="gpt-4o",
        tokens_used=10,
        cost_usd=Decimal("0.00001"),
    )
    db.session.add(insight)
    db.session.commit()
    return insight.id


def _register_and_login(client, prefix: str = "fb") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    client.post(
        "/auth/register",
        json={"name": prefix, "email": email, "password": "StrongPass@123"},
    )
    login = client.post(
        "/auth/login", json={"email": email, "password": "StrongPass@123"}
    )
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


_RATINGS = {"relevance": 5, "truthfulness": 4, "depth": 4, "usefulness": 5}


class TestFeedbackService:
    def test_submit_creates_feedback_for_owned_insight(self, app) -> None:
        with app.app_context():
            from app.application.services.ai_insight_feedback_service import (
                submit_insight_feedback,
            )

            user_id = _make_user()
            insight_id = _make_insight(user_id)
            result = submit_insight_feedback(
                user_id=user_id,
                insight_id=insight_id,
                data={**_RATINGS, "comment": "Muito útil"},
            )
            assert result["relevance"] == 5
            assert result["comment"] == "Muito útil"
            assert (
                db.session.query(AIInsightFeedback)
                .filter_by(user_id=user_id, insight_id=insight_id)
                .count()
                == 1
            )

    def test_submit_is_upsert(self, app) -> None:
        with app.app_context():
            from app.application.services.ai_insight_feedback_service import (
                submit_insight_feedback,
            )

            user_id = _make_user()
            insight_id = _make_insight(user_id)
            submit_insight_feedback(
                user_id=user_id, insight_id=insight_id, data={**_RATINGS}
            )
            submit_insight_feedback(
                user_id=user_id,
                insight_id=insight_id,
                data={**_RATINGS, "relevance": 1, "comment": "revisado"},
            )
            rows = (
                db.session.query(AIInsightFeedback)
                .filter_by(user_id=user_id, insight_id=insight_id)
                .all()
            )
            assert len(rows) == 1
            assert rows[0].relevance == 1
            assert rows[0].comment == "revisado"

    def test_submit_rejects_foreign_insight(self, app) -> None:
        with app.app_context():
            from app.application.services.ai_insight_feedback_service import (
                AIInsightFeedbackError,
                submit_insight_feedback,
            )

            owner = _make_user()
            other = _make_user()
            insight_id = _make_insight(owner)
            with pytest.raises(AIInsightFeedbackError) as exc:
                submit_insight_feedback(
                    user_id=other, insight_id=insight_id, data={**_RATINGS}
                )
            assert exc.value.status_code == 404

    def test_aggregate_averages(self, app) -> None:
        with app.app_context():
            from app.application.services.ai_insight_feedback_service import (
                get_insight_feedback_aggregate,
                submit_insight_feedback,
            )

            for relevance in (2, 4):
                user_id = _make_user()
                insight_id = _make_insight(user_id)
                submit_insight_feedback(
                    user_id=user_id,
                    insight_id=insight_id,
                    data={**_RATINGS, "relevance": relevance},
                )
            agg = get_insight_feedback_aggregate()
            assert agg["total_feedback"] >= 2
            assert agg["averages"]["relevance"] is not None


class TestFeedbackREST:
    def test_post_feedback_returns_201(self, app, client) -> None:
        from flask_jwt_extended import decode_token

        token = _register_and_login(client)
        with app.app_context():
            user_id = uuid.UUID(decode_token(token)["sub"])
            insight_id = _make_insight(user_id)

        resp = client.post(
            f"/ai/insights/{insight_id}/feedback",
            json={**_RATINGS, "comment": "ótimo"},
            headers=_auth(token),
        )
        assert resp.status_code == 201, resp.get_json()
        assert resp.get_json()["data"]["relevance"] == 5

    def test_post_feedback_out_of_range_returns_400(self, app, client) -> None:
        from flask_jwt_extended import decode_token

        token = _register_and_login(client)
        with app.app_context():
            user_id = uuid.UUID(decode_token(token)["sub"])
            insight_id = _make_insight(user_id)

        resp = client.post(
            f"/ai/insights/{insight_id}/feedback",
            json={**_RATINGS, "relevance": 9},
            headers=_auth(token),
        )
        assert resp.status_code == 400
        assert resp.get_json()["error"]["code"] == "VALIDATION_ERROR"

    def test_post_feedback_foreign_insight_returns_404(self, app, client) -> None:
        token = _register_and_login(client)
        with app.app_context():
            other = _make_user()
            insight_id = _make_insight(other)

        resp = client.post(
            f"/ai/insights/{insight_id}/feedback",
            json={**_RATINGS},
            headers=_auth(token),
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"]["code"] == "AI_INSIGHT_NOT_FOUND"


class TestFeedbackGraphQL:
    def test_submit_feedback_mutation(self, app, client) -> None:
        from flask_jwt_extended import decode_token

        token = _register_and_login(client)
        with app.app_context():
            user_id = uuid.UUID(decode_token(token)["sub"])
            insight_id = _make_insight(user_id)

        query = (
            "mutation { submitAiInsightFeedback("
            f'insightId: "{insight_id}", relevance: 5, truthfulness: 4, '
            'depth: 3, usefulness: 5, comment: "bom") '
            "{ ok relevance comment } }"
        )
        resp = client.post(
            "/graphql",
            json={"query": query},
            headers={"Authorization": f"Bearer {token}"},
        )
        body = resp.get_json()
        assert "errors" not in body, body
        payload = body["data"]["submitAiInsightFeedback"]
        assert payload["ok"] is True
        assert payload["relevance"] == 5
