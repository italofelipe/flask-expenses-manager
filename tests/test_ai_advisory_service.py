"""Tests for AIAdvisoryService and AI advisory controller endpoints (#1206).

Coverage areas:
- LLMResponse dataclass and estimated_cost_usd property
- StubLLMProvider.generate_with_usage()
- AIAdvisoryService.generate_spending_insights()
- AIAdvisoryService.generate_goal_projection_narrative()
- AIAdvisoryService.generate_weekly_summary_narrative()
- LLMAuditLog persistence
- Entitlement gate (premium required)
- GET /ai/insights/spending — auth, entitlement, happy path
- POST /ai/goals/<goal_id>/projection — auth, entitlement, validation, happy path
- GET /ai/insights/weekly-summary — auth, entitlement, happy path
- LLMProviderError propagation
- Goal not found raises ValueError → 404
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_provider import LLMProviderError, LLMResponse, StubLLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _grant_entitlement(app, user_id: uuid.UUID, feature_key: str) -> None:
    """Grant an entitlement directly in the DB for test setup."""
    with app.app_context():
        from app.extensions.database import db
        from app.models.entitlement import Entitlement, EntitlementSource

        ent = Entitlement(
            user_id=user_id,
            feature_key=feature_key,
            source=EntitlementSource.MANUAL,
            expires_at=None,
        )
        db.session.add(ent)
        db.session.commit()


def _revoke_premium_entitlements(app, user_id: uuid.UUID) -> None:
    """Revoke all premium-only entitlements so user is effectively on free plan."""
    with app.app_context():
        from app.services.entitlement_service import deactivate_premium

        deactivate_premium(user_id)


def _get_current_user_id(app, token: str) -> uuid.UUID:
    """Extract user UUID from the JWT token."""
    with app.app_context():
        from flask_jwt_extended import decode_token

        decoded = decode_token(token)
        return uuid.UUID(decoded["sub"])


# ---------------------------------------------------------------------------
# LLMResponse tests
# ---------------------------------------------------------------------------


class TestLLMResponse:
    def test_known_model_cost(self) -> None:
        resp = LLMResponse(
            content="test",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            model="gpt-4o-mini",
            latency_ms=100,
        )
        # 1M prompt * 0.15 + 1M completion * 0.60 = 0.75
        assert abs(resp.estimated_cost_usd - 0.75) < 1e-6

    def test_unknown_model_fallback_cost(self) -> None:
        resp = LLMResponse(
            content="test",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            model="unknown-model",
            latency_ms=50,
        )
        # fallback: 0.002 + 0.008 = 0.010
        assert abs(resp.estimated_cost_usd - 0.010) < 1e-6

    def test_zero_tokens_zero_cost(self) -> None:
        resp = LLMResponse(
            content="",
            prompt_tokens=0,
            completion_tokens=0,
            total_tokens=0,
            model="gpt-4o-mini",
            latency_ms=0,
        )
        assert resp.estimated_cost_usd == 0.0

    def test_claude_model_cost(self) -> None:
        resp = LLMResponse(
            content="ok",
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            total_tokens=2_000_000,
            model="claude-haiku-4-5-20251001",
            latency_ms=200,
        )
        # 1M * 0.25 + 1M * 1.25 = 1.50
        assert abs(resp.estimated_cost_usd - 1.50) < 1e-6


# ---------------------------------------------------------------------------
# StubLLMProvider tests
# ---------------------------------------------------------------------------


class TestStubLLMProvider:
    def test_generate_returns_string(self) -> None:
        provider = StubLLMProvider()
        result = provider.generate("any prompt")
        assert isinstance(result, str)
        assert len(result) > 10

    def test_generate_with_usage_returns_llm_response(self) -> None:
        provider = StubLLMProvider()
        result = provider.generate_with_usage("any prompt")
        assert isinstance(result, LLMResponse)
        assert result.content == provider.generate("any prompt")
        assert result.model == "stub"
        assert result.total_tokens > 0
        assert result.latency_ms == 0

    def test_generate_and_generate_with_usage_content_match(self) -> None:
        provider = StubLLMProvider()
        assert provider.generate("x") == provider.generate_with_usage("x").content


# ---------------------------------------------------------------------------
# AIAdvisoryService unit tests (mocked provider)
# ---------------------------------------------------------------------------


class TestAIAdvisoryServiceSpendingInsights:
    def test_generate_spending_insights_returns_expected_keys(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            result = service.generate_spending_insights()
            assert "insights" in result
            assert "tokens_used" in result
            assert "cost_usd" in result
            assert "month" in result
            assert "model" in result

    def test_generate_spending_insights_with_explicit_month(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            result = service.generate_spending_insights(month="2026-01")
            assert result["month"] == "2026-01"

    def test_llm_provider_error_propagates(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            broken = MagicMock()
            broken.generate_with_usage.side_effect = LLMProviderError("fail")

            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=broken)
            with pytest.raises(LLMProviderError):
                service.generate_spending_insights()

    def test_audit_log_created_on_success(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            provider = StubLLMProvider()
            from app.models.llm_audit_log import LLMAuditLog
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            service.generate_spending_insights()

            log_row = LLMAuditLog.query.filter_by(
                user_id=user_id, endpoint="spending_insights"
            ).first()
            assert log_row is not None
            assert log_row.model == "stub"
            assert log_row.total_tokens > 0


class TestAIAdvisoryServiceGoalProjection:
    def _create_goal(self, app, user_id: uuid.UUID) -> uuid.UUID:
        with app.app_context():
            from app.extensions.database import db
            from app.models.goal import Goal

            goal = Goal(
                user_id=user_id,
                title="Viagem Europa",
                target_amount=Decimal("15000.00"),
                current_amount=Decimal("3000.00"),
                status="active",
            )
            db.session.add(goal)
            db.session.commit()
            return goal.id  # type: ignore[return-value]

    def test_goal_not_found_raises_value_error(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            with pytest.raises(ValueError, match="not found"):
                service.generate_goal_projection_narrative(
                    goal_id=uuid.uuid4(),
                    user_context="Quero viajar",
                    monthly_contribution=Decimal("500"),
                )

    def test_goal_wrong_user_raises_value_error(self, app) -> None:
        with app.app_context():
            owner_id = uuid.uuid4()
            other_id = uuid.uuid4()
            goal_id = self._create_goal(app, owner_id)

            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=other_id, llm_provider=provider)
            with pytest.raises(ValueError, match="not found"):
                service.generate_goal_projection_narrative(
                    goal_id=goal_id,
                    user_context="teste",
                    monthly_contribution=Decimal("500"),
                )

    def test_happy_path_returns_required_keys(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            goal_id = self._create_goal(app, user_id)
            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            result = service.generate_goal_projection_narrative(
                goal_id=goal_id,
                user_context="Quero viajar para Europa em 2028",
                monthly_contribution=Decimal("500"),
            )
            assert "narrative" in result
            assert "tokens_used" in result
            assert "cost_usd" in result
            assert "projection" in result
            assert "model" in result
            assert isinstance(result["projection"], dict)


class TestAIAdvisoryServiceWeeklySummary:
    def test_weekly_summary_returns_required_keys(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            provider = StubLLMProvider()
            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=provider)
            result = service.generate_weekly_summary_narrative()
            assert "narrative" in result
            assert "tokens_used" in result
            assert "cost_usd" in result
            assert "summary" in result
            assert "model" in result

    def test_llm_error_propagates_in_weekly_summary(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            broken = MagicMock()
            broken.generate_with_usage.side_effect = LLMProviderError("fail")

            from app.services.ai_advisory_service import AIAdvisoryService

            service = AIAdvisoryService(user_id=user_id, llm_provider=broken)
            with pytest.raises(LLMProviderError):
                service.generate_weekly_summary_narrative()


# ---------------------------------------------------------------------------
# HTTP endpoint tests
# ---------------------------------------------------------------------------


class TestAISpendingInsightsEndpoint:
    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/ai/insights/spending")
        assert resp.status_code == 401

    def test_authenticated_free_user_returns_403(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-free")
        user_id = _get_current_user_id(app, token)
        # New registrations may get a trial; revoke premium to simulate free plan.
        _revoke_premium_entitlements(app, user_id)
        resp = client.get("/ai/insights/spending", headers=_auth(token))
        assert resp.status_code == 403

    def test_premium_user_returns_200(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-prem")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.get("/ai/insights/spending", headers=_auth(token))
        assert resp.status_code == 200

    def test_response_has_required_keys(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-keys")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.get("/ai/insights/spending", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        for key in ("insights", "tokens_used", "cost_usd", "month", "model"):
            assert key in data, f"Missing key: {key}"

    def test_month_param_accepted(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-month")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.get("/ai/insights/spending?month=2026-01", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert data["month"] == "2026-01"

    def test_llm_error_returns_500(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-err")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService.generate_spending_insights",
            side_effect=LLMProviderError("provider down"),
        ):
            resp = client.get("/ai/insights/spending", headers=_auth(token))
            assert resp.status_code == 500


class TestAIGoalProjectionEndpoint:
    def _create_goal_via_api(self, client, token: str) -> str:
        resp = client.post(
            "/goals",
            json={
                "title": "Meta Teste",
                "target_amount": 10000,
                "current_amount": 1000,
                "status": "active",
            },
            headers=_auth(token),
        )
        assert resp.status_code in (200, 201)
        data = resp.get_json()
        # Extract goal id from response
        goal_data = data.get("data", {}).get("goal") or data.get("goal") or {}
        return goal_data.get("id", "")

    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.post(
            f"/ai/goals/{uuid.uuid4()}/projection",
            json={"monthly_contribution": 500, "user_context": "teste"},
        )
        assert resp.status_code == 401

    def test_free_user_returns_403(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-gfree")
        user_id = _get_current_user_id(app, token)
        _revoke_premium_entitlements(app, user_id)
        goal_id = str(uuid.uuid4())
        resp = client.post(
            f"/ai/goals/{goal_id}/projection",
            json={"monthly_contribution": 500, "user_context": "teste"},
            headers=_auth(token),
        )
        assert resp.status_code == 403

    def test_invalid_goal_id_returns_400(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-gbad")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.post(
            "/ai/goals/not-a-uuid/projection",
            json={"monthly_contribution": 500, "user_context": "teste"},
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_missing_monthly_contribution_returns_400(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-gnomc")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.post(
            f"/ai/goals/{uuid.uuid4()}/projection",
            json={"user_context": "teste"},
            headers=_auth(token),
        )
        assert resp.status_code == 400

    def test_goal_not_found_returns_404(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-g404")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.post(
            f"/ai/goals/{uuid.uuid4()}/projection",
            json={"monthly_contribution": 500, "user_context": "teste"},
            headers=_auth(token),
        )
        assert resp.status_code == 404

    def test_happy_path_returns_200_with_narrative(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-gok")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        # Create goal directly in DB
        with app.app_context():
            from app.extensions.database import db
            from app.models.goal import Goal

            goal = Goal(
                user_id=user_id,
                title="Carro Novo",
                target_amount=Decimal("50000"),
                current_amount=Decimal("5000"),
                status="active",
            )
            db.session.add(goal)
            db.session.commit()
            goal_id = str(goal.id)

        resp = client.post(
            f"/ai/goals/{goal_id}/projection",
            json={
                "monthly_contribution": 1000,
                "user_context": "Quero comprar um carro",
            },
            headers=_auth(token),
        )
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        assert "narrative" in data
        assert "projection" in data


class TestAIWeeklySummaryEndpoint:
    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/ai/insights/weekly-summary")
        assert resp.status_code == 401

    def test_free_user_returns_403(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-wfree")
        user_id = _get_current_user_id(app, token)
        _revoke_premium_entitlements(app, user_id)
        resp = client.get("/ai/insights/weekly-summary", headers=_auth(token))
        assert resp.status_code == 403

    def test_premium_user_returns_200(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-wprem")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.get("/ai/insights/weekly-summary", headers=_auth(token))
        assert resp.status_code == 200

    def test_response_has_required_keys(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-wkeys")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        resp = client.get("/ai/insights/weekly-summary", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        for key in ("narrative", "tokens_used", "cost_usd", "summary", "model"):
            assert key in data, f"Missing key: {key}"

    def test_llm_error_returns_500(self, app, client) -> None:
        token = _register_and_login(client, prefix="ai-werr")
        user_id = _get_current_user_id(app, token)
        _grant_entitlement(app, user_id, "advanced_simulations")

        with patch(
            "app.services.ai_advisory_service.AIAdvisoryService.generate_weekly_summary_narrative",
            side_effect=LLMProviderError("provider down"),
        ):
            resp = client.get("/ai/insights/weekly-summary", headers=_auth(token))
            assert resp.status_code == 500


# ---------------------------------------------------------------------------
# LLMAuditLog model tests
# ---------------------------------------------------------------------------


class TestLLMAuditLogModel:
    def test_audit_log_can_be_created_and_retrieved(self, app) -> None:
        with app.app_context():
            from app.extensions.database import db
            from app.models.llm_audit_log import LLMAuditLog

            user_id = uuid.uuid4()
            log_row = LLMAuditLog(
                user_id=user_id,
                endpoint="spending_insights",
                model="stub",
                prompt="test prompt",
                response_text="test response",
                prompt_tokens=100,
                completion_tokens=50,
                total_tokens=150,
                estimated_cost_usd=0.0001,
                latency_ms=50,
            )
            db.session.add(log_row)
            db.session.commit()

            retrieved = LLMAuditLog.query.filter_by(user_id=user_id).first()
            assert retrieved is not None
            assert retrieved.endpoint == "spending_insights"
            assert retrieved.model == "stub"
            assert retrieved.total_tokens == 150

    def test_audit_log_repr(self, app) -> None:
        with app.app_context():
            from app.models.llm_audit_log import LLMAuditLog

            user_id = uuid.uuid4()
            log_row = LLMAuditLog(
                user_id=user_id,
                endpoint="weekly_summary",
                model="gpt-4o-mini",
                prompt="p",
                response_text="r",
                total_tokens=99,
            )
            r = repr(log_row)
            assert "LLMAuditLog" in r
            assert "weekly_summary" in r
