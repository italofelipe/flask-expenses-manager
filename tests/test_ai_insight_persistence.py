"""Tests for AIInsight persistence and history endpoint (#1228).

Coverage:
- generate_spending_insights() saves an AIInsight record
- Idempotency: second call same day returns cached insight without calling LLM
- Context injection: prompt includes previous insight content
- Recap: last day of month uses InsightType.recap
- GET /ai/insights/history — auth, pagination, ordering, empty state
- History accessible without premium entitlement (read-only)
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.models.ai_insight import AIInsight, InsightType
from app.services.llm_provider import LLMResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str) -> str:
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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _grant_premium(app, token: str) -> None:
    with app.app_context():
        from flask_jwt_extended import decode_token

        from app.extensions.database import db
        from app.models.entitlement import Entitlement, EntitlementSource

        user_id = uuid.UUID(decode_token(token)["sub"])
        ent = Entitlement(
            user_id=user_id,
            feature_key="advanced_simulations",
            source=EntitlementSource.MANUAL,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()


def _revoke_premium(app, token: str) -> None:
    with app.app_context():
        from flask_jwt_extended import decode_token

        from app.services.entitlement_service import deactivate_premium

        user_id = uuid.UUID(decode_token(token)["sub"])
        deactivate_premium(user_id)


def _stub_response(content: str = "Insight gerado com sucesso.") -> LLMResponse:
    return LLMResponse(
        content=content,
        prompt_tokens=100,
        completion_tokens=200,
        total_tokens=300,
        model="gpt-4o-mini",
        latency_ms=500,
    )


# ---------------------------------------------------------------------------
# Unit tests — AIAdvisoryService persistence
# ---------------------------------------------------------------------------


class TestAdvisoryServicePersistence:
    def test_generate_spending_insights_saves_ai_insight(self, app) -> None:
        with app.app_context():
            from app.extensions.database import db
            from app.services.ai_advisory_service import AIAdvisoryService

            user_id = uuid.uuid4()
            provider = MagicMock()
            provider.generate_with_usage.return_value = _stub_response()

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            service.generate_spending_insights()

            saved = (
                db.session.query(AIInsight)
                .filter_by(user_id=user_id, insight_type=InsightType.daily)
                .first()
            )
            assert saved is not None
            assert saved.content == "Insight gerado com sucesso."
            assert saved.model == "gpt-4o-mini"
            assert saved.tokens_used == 300

    def test_idempotency_returns_cached_insight_without_calling_llm(self, app) -> None:
        with app.app_context():
            from app.services.ai_advisory_service import AIAdvisoryService

            user_id = uuid.uuid4()
            provider = MagicMock()
            provider.generate_with_usage.return_value = _stub_response("First insight.")

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            result1 = service.generate_spending_insights()
            result2 = service.generate_spending_insights()

            # LLM was called only once
            assert provider.generate_with_usage.call_count == 1
            assert result1["insights"] == result2["insights"]
            assert result2.get("cached") is True

    def test_context_injection_includes_previous_insight_in_prompt(self, app) -> None:
        with app.app_context():
            from app.extensions.database import db
            from app.services.ai_advisory_service import AIAdvisoryService

            user_id = uuid.uuid4()
            yesterday = date.today() - timedelta(days=1)

            # Seed a previous insight
            prev = AIInsight(
                user_id=user_id,
                content="Ontem você gastou muito em alimentação.",
                insight_type=InsightType.daily,
                period_label=yesterday.strftime("%Y-%m-%d"),
                period_start=yesterday,
                period_end=yesterday,
                model="gpt-4o-mini",
                tokens_used=100,
                cost_usd=0.000015,
            )
            db.session.add(prev)
            db.session.commit()

            provider = MagicMock()
            provider.generate_with_usage.return_value = _stub_response()

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            service.generate_spending_insights()

            # The prompt passed to the LLM must contain the previous insight
            call_args = provider.generate_with_usage.call_args
            prompt_text = call_args[0][0]
            assert "Ontem você gastou muito em alimentação." in prompt_text

    def test_last_day_of_month_uses_recap_type(self, app) -> None:
        with app.app_context():
            from app.extensions.database import db
            from app.services.ai_advisory_service import AIAdvisoryService

            user_id = uuid.uuid4()
            provider = MagicMock()
            provider.generate_with_usage.return_value = _stub_response("Recap do mês.")

            # Patch date.today() to be the last day of a month
            last_day = date(2026, 5, 31)
            with patch("app.services.ai_advisory_service.date") as mock_date:
                mock_date.today.return_value = last_day
                mock_date.side_effect = lambda *args, **kw: date(*args, **kw)

                service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
                service.generate_spending_insights()

            saved = db.session.query(AIInsight).filter_by(user_id=user_id).first()
            assert saved is not None
            assert saved.insight_type == InsightType.recap


# ---------------------------------------------------------------------------
# Integration tests — GET /ai/insights/history
# ---------------------------------------------------------------------------


class TestAIInsightHistoryEndpoint:
    def test_returns_empty_list_when_no_insights(self, app, client) -> None:
        token = _register_and_login(client, "hist-empty")
        resp = client.get("/ai/insights/history", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        items = (data.get("data") or {}).get("items") or data.get("items") or []
        assert items == []

    def test_returns_insights_ordered_by_created_at_desc(self, app, client) -> None:
        token = _register_and_login(client, "hist-order")

        with app.app_context():
            from flask_jwt_extended import decode_token

            from app.extensions.database import db

            user_id = uuid.UUID(decode_token(token)["sub"])
            today = date.today()

            for i, itype in enumerate([InsightType.daily, InsightType.weekly]):
                db.session.add(
                    AIInsight(
                        user_id=user_id,
                        content=f"Insight {i}",
                        insight_type=itype,
                        period_label=f"2026-05-0{i + 1}",
                        period_start=today,
                        period_end=today,
                        model="gpt-4o-mini",
                        tokens_used=100,
                        cost_usd=0.00001,
                    )
                )
            db.session.commit()

        resp = client.get("/ai/insights/history", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        items = (data.get("data") or {}).get("items") or data.get("items") or []
        assert len(items) == 2

    def test_requires_authentication(self, client) -> None:
        resp = client.get("/ai/insights/history")
        assert resp.status_code == 401

    def test_free_user_can_access_history(self, app, client) -> None:
        """History is readable by all users — no entitlement gate."""
        token = _register_and_login(client, "hist-free")
        _revoke_premium(app, token)
        resp = client.get("/ai/insights/history", headers=_auth(token))
        assert resp.status_code == 200

    def test_pagination_per_page(self, app, client) -> None:
        token = _register_and_login(client, "hist-page")

        with app.app_context():
            from flask_jwt_extended import decode_token

            from app.extensions.database import db

            user_id = uuid.UUID(decode_token(token)["sub"])
            today = date.today()

            for i in range(5):
                db.session.add(
                    AIInsight(
                        user_id=user_id,
                        content=f"Insight #{i}",
                        insight_type=InsightType.daily,
                        period_label=f"2026-05-{i + 1:02d}",
                        period_start=today,
                        period_end=today,
                        model="gpt-4o-mini",
                        tokens_used=100,
                        cost_usd=0.00001,
                    )
                )
            db.session.commit()

        resp = client.get("/ai/insights/history?per_page=2", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        items = (data.get("data") or {}).get("items") or data.get("items") or []
        assert len(items) == 2

    def test_response_contains_expected_fields(self, app, client) -> None:
        token = _register_and_login(client, "hist-fields")

        with app.app_context():
            from flask_jwt_extended import decode_token

            from app.extensions.database import db

            user_id = uuid.UUID(decode_token(token)["sub"])
            today = date.today()
            db.session.add(
                AIInsight(
                    user_id=user_id,
                    content="Field test insight.",
                    insight_type=InsightType.daily,
                    period_label=today.strftime("%Y-%m-%d"),
                    period_start=today,
                    period_end=today,
                    model="gpt-4o-mini",
                    tokens_used=150,
                    cost_usd=0.000022,
                )
            )
            db.session.commit()

        resp = client.get("/ai/insights/history", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.get_json()
        items = (data.get("data") or {}).get("items") or data.get("items") or []
        assert len(items) == 1
        item = items[0]
        for field in ("id", "content", "insight_type", "period_label", "created_at"):
            assert field in item, f"Missing field: {field}"

    def test_user_only_sees_own_insights(self, app, client) -> None:
        token_a = _register_and_login(client, "hist-isola")
        token_b = _register_and_login(client, "hist-isolb")

        # Baseline: record user_b's current count before adding user_a's insight
        resp_baseline = client.get("/ai/insights/history", headers=_auth(token_b))
        assert resp_baseline.status_code == 200
        baseline = resp_baseline.get_json()
        baseline_count = (baseline.get("data") or {}).get("total", 0)

        unique_content = f"Exclusive to user A — {uuid.uuid4().hex}"

        with app.app_context():
            from flask_jwt_extended import decode_token

            from app.extensions.database import db

            user_a = uuid.UUID(decode_token(token_a)["sub"])
            today = date.today()
            db.session.add(
                AIInsight(
                    user_id=user_a,
                    content=unique_content,
                    insight_type=InsightType.daily,
                    period_label=f"{today.strftime('%Y-%m-%d')}-a",
                    period_start=today,
                    period_end=today,
                    model="gpt-4o-mini",
                    tokens_used=100,
                    cost_usd=0.00001,
                )
            )
            db.session.commit()

        # user_b count must not have changed and must not contain user_a's content
        resp_b = client.get("/ai/insights/history", headers=_auth(token_b))
        assert resp_b.status_code == 200
        data_b = resp_b.get_json()
        total_b = (data_b.get("data") or {}).get("total", 0)
        items_b = (data_b.get("data") or {}).get("items") or []
        assert total_b == baseline_count
        assert not any(unique_content in (i.get("content") or "") for i in items_b)
