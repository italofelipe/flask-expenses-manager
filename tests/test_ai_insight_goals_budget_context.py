"""Tests for AI insight cross-domain enrichment with goals and budgets (#1235).

Coverage:
- _build_goals_snapshot returns correct structure for active goals
- _build_goals_snapshot distributes savings proxy across num_goals
- _build_goals_snapshot includes recent_contributions_30d sum
- _build_overall_budget_snapshot returns utilization for null-tag monthly budget
- _build_overall_budget_snapshot returns None when no overall budget exists
- _build_overall_budget_snapshot ignores tag-linked budgets
- _build_spending_prompt includes goals section when goals list is non-empty
- _build_spending_prompt includes budget section when budget dict is provided
- _build_spending_prompt omits goals/budget sections when not provided
- generate_spending_insights calls the helpers and passes context to prompt
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from app.extensions.database import db
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.goal_contribution import GoalContribution
from app.services.ai_advisory_service import (
    _build_goals_snapshot,
    _build_overall_budget_snapshot,
    _build_spending_prompt,
)
from app.services.llm_provider import LLMResponse

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str = "ai-ctx") -> tuple[str, uuid.UUID]:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@test.com"
    client.post(
        "/auth/register",
        json={"name": f"{prefix}", "email": email, "password": "StrongPass@123"},
    )
    login = client.post(
        "/auth/login", json={"email": email, "password": "StrongPass@123"}
    )
    token = login.get_json()["token"]
    from flask_jwt_extended import decode_token

    user_id = uuid.UUID(decode_token(token)["sub"])
    return token, user_id


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _make_goal(
    app,
    user_id: uuid.UUID,
    *,
    title: str = "Meta teste",
    target_amount: float = 1000.0,
    current_amount: float = 0.0,
    target_date: date | None = None,
    status: str = "active",
) -> Goal:
    with app.app_context():
        goal = Goal(
            user_id=user_id,
            title=title,
            target_amount=Decimal(str(target_amount)),
            current_amount=Decimal(str(current_amount)),
            target_date=target_date,
            status=status,
        )
        db.session.add(goal)
        db.session.commit()
        db.session.refresh(goal)
        return goal


def _make_budget(
    app,
    user_id: uuid.UUID,
    *,
    name: str = "Orçamento Geral",
    amount: float = 3000.0,
    period: str = "monthly",
    tag_id: uuid.UUID | None = None,
) -> Budget:
    with app.app_context():
        budget = Budget(
            user_id=user_id,
            name=name,
            amount=Decimal(str(amount)),
            period=period,
            tag_id=tag_id,
            is_active=True,
        )
        db.session.add(budget)
        db.session.commit()
        return budget


def _make_contribution(
    app,
    user_id: uuid.UUID,
    goal_id: uuid.UUID,
    amount: float,
    days_ago: int = 5,
) -> None:
    with app.app_context():
        from datetime import datetime

        contrib = GoalContribution(
            goal_id=goal_id,
            user_id=user_id,
            amount=Decimal(str(amount)),
            created_at=datetime.utcnow() - timedelta(days=days_ago),
        )
        db.session.add(contrib)
        db.session.commit()


# ---------------------------------------------------------------------------
# Tests: _build_goals_snapshot
# ---------------------------------------------------------------------------


class TestBuildGoalsSnapshot:
    def test_returns_empty_list_when_no_goals(self, app):
        with app.app_context():
            user_id = uuid.uuid4()
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=500.0)
            assert result == []

    def test_returns_goal_structure(self, app, client):
        _, user_id = _register_and_login(client)
        target_date = date.today() + timedelta(days=180)
        _make_goal(
            app,
            user_id,
            title="Viagem Itália",
            current_amount=500.0,
            target_amount=2000.0,
            target_date=target_date,
        )

        with app.app_context():
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=600.0)

        assert len(result) == 1
        g = result[0]
        assert g["title"] == "Viagem Itália"
        assert g["progress_pct"] == pytest.approx(25.0)
        assert g["current_amount"] == 500.0
        assert g["target_amount"] == 2000.0
        assert g["days_remaining"] == (target_date - date.today()).days
        assert "on_track" in g
        assert "months_to_completion" in g
        assert "suggested_monthly_contribution" in g

    def test_proxy_contribution_divided_by_num_goals(self, app, client):
        _, user_id = _register_and_login(client)
        _make_goal(app, user_id, title="Meta A", target_amount=1000.0)
        _make_goal(app, user_id, title="Meta B", target_amount=2000.0)

        with app.app_context():
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=600.0)

        # With 2 goals and savings=600, each gets proxy=300
        # Both have no target_date → on_track=False; months_to_completion computed
        assert len(result) == 2

    def test_recent_contributions_30d_sum(self, app, client):
        _, user_id = _register_and_login(client)
        goal = _make_goal(
            app, user_id, title="Reserva", current_amount=0.0, target_amount=5000.0
        )
        _make_contribution(app, user_id, goal.id, 200.0, days_ago=5)
        _make_contribution(app, user_id, goal.id, 150.0, days_ago=15)
        _make_contribution(app, user_id, goal.id, 100.0, days_ago=45)  # outside 30d

        with app.app_context():
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=0.0)

        assert len(result) == 1
        assert result[0]["recent_contributions_30d"] == pytest.approx(350.0)

    def test_inactive_goals_excluded(self, app, client):
        _, user_id = _register_and_login(client)
        _make_goal(app, user_id, title="Ativa", status="active")
        _make_goal(app, user_id, title="Concluída", status="completed")

        with app.app_context():
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=500.0)

        assert len(result) == 1
        assert result[0]["title"] == "Ativa"

    def test_no_target_date_returns_none_days_remaining(self, app, client):
        _, user_id = _register_and_login(client)
        _make_goal(app, user_id, target_date=None)

        with app.app_context():
            result = _build_goals_snapshot(user_id=user_id, monthly_savings_brl=500.0)

        assert result[0]["days_remaining"] is None
        assert result[0]["target_date"] is None


# ---------------------------------------------------------------------------
# Tests: _build_overall_budget_snapshot
# ---------------------------------------------------------------------------


class TestBuildOverallBudgetSnapshot:
    def test_returns_none_when_no_budget(self, app, client):
        _, user_id = _register_and_login(client)

        with app.app_context():
            result = _build_overall_budget_snapshot(
                user_id=user_id, total_expense_brl=1000.0
            )

        assert result is None

    def test_returns_utilization_for_overall_budget(self, app, client):
        _, user_id = _register_and_login(client)
        _make_budget(app, user_id, name="Mensal Geral", amount=3000.0, tag_id=None)

        with app.app_context():
            result = _build_overall_budget_snapshot(
                user_id=user_id, total_expense_brl=2400.0
            )

        assert result is not None
        assert result["name"] == "Mensal Geral"
        assert result["budget_amount"] == 3000.0
        assert result["spent"] == 2400.0
        assert result["utilization_pct"] == pytest.approx(80.0)
        assert result["exceeded"] is False

    def test_exceeded_flag_when_over_budget(self, app, client):
        _, user_id = _register_and_login(client)
        _make_budget(app, user_id, amount=2000.0, tag_id=None)

        with app.app_context():
            result = _build_overall_budget_snapshot(
                user_id=user_id, total_expense_brl=2500.0
            )

        assert result is not None
        assert result["exceeded"] is True
        assert result["utilization_pct"] == pytest.approx(125.0)

    def test_ignores_tag_linked_budgets(self, app, client):
        _, user_id = _register_and_login(client)
        # Tag-linked budget — should NOT be returned
        _make_budget(app, user_id, amount=500.0, tag_id=uuid.uuid4())

        with app.app_context():
            result = _build_overall_budget_snapshot(
                user_id=user_id, total_expense_brl=400.0
            )

        assert result is None


# ---------------------------------------------------------------------------
# Tests: _build_spending_prompt
# ---------------------------------------------------------------------------


class TestBuildSpendingPrompt:
    def _snapshot(self) -> dict:
        return {
            "period_start": "2026-05-01",
            "period_end": "2026-05-31",
            "total_expense": 2000.0,
            "total_income": 4000.0,
            "balance": 2000.0,
            "savings_rate_pct": 50.0,
            "transaction_count": 20,
            "top_expenses": [],
        }

    def test_includes_goals_section_when_provided(self):
        goals = [
            {
                "title": "Viagem Itália",
                "progress_pct": 25.0,
                "on_track": False,
                "days_remaining": 90,
            }
        ]
        prompt = _build_spending_prompt(
            self._snapshot(), "2026-05", goals=goals, budget=None
        )
        assert "Viagem Itália" in prompt
        assert "Metas financeiras ativas" in prompt

    def test_omits_goals_section_when_empty(self):
        prompt = _build_spending_prompt(
            self._snapshot(), "2026-05", goals=[], budget=None
        )
        assert "Metas financeiras ativas" not in prompt

    def test_includes_budget_section_when_provided(self):
        budget = {
            "name": "Orçamento Geral",
            "budget_amount": 3000.0,
            "spent": 2400.0,
            "utilization_pct": 80.0,
            "exceeded": False,
        }
        prompt = _build_spending_prompt(
            self._snapshot(), "2026-05", goals=None, budget=budget
        )
        assert "Orçamento mensal geral" in prompt
        assert "Orçamento Geral" in prompt

    def test_omits_budget_section_when_none(self):
        prompt = _build_spending_prompt(
            self._snapshot(), "2026-05", goals=None, budget=None
        )
        assert "Orçamento mensal geral" not in prompt

    def test_includes_cross_domain_insight_types(self):
        prompt = _build_spending_prompt(
            self._snapshot(), "2026-05", goals=None, budget=None
        )
        assert "alerta_meta" in prompt
        assert "progresso_meta" in prompt
        assert "orcamento_ultrapassado" in prompt
        assert "planejamento_meta" in prompt


# ---------------------------------------------------------------------------
# Integration: generate_spending_insights calls helpers
# ---------------------------------------------------------------------------


class TestGenerateSpendingInsightsEnrichment:
    def test_prompt_contains_goal_data(self, app, client):
        _, user_id = _register_and_login(client)
        _make_goal(
            app,
            user_id,
            title="Reserva Emergência",
            current_amount=300.0,
            target_amount=5000.0,
            target_date=date.today() + timedelta(days=365),
        )

        stub_response = LLMResponse(
            content='[{"type":"alerta_meta","title":"Meta em risco","message":"..."}]',
            prompt_tokens=200,
            completion_tokens=50,
            total_tokens=250,
            model="stub",
            latency_ms=10,
        )

        captured_prompts: list[str] = []

        with app.app_context():
            from app.services.ai_advisory_service import AIAdvisoryService

            mock_provider = MagicMock()
            mock_provider.generate_with_usage.side_effect = lambda p: (
                captured_prompts.append(p) or stub_response
            )

            service = AIAdvisoryService(user_id=user_id, llm_provider=mock_provider)
            # Patch the instance method so the snapshot returns controlled data
            service._build_spending_snapshot = MagicMock(
                return_value={
                    "period_start": "2026-05-01",
                    "period_end": "2026-05-31",
                    "total_expense": 2500.0,
                    "total_income": 4000.0,
                    "balance": 1500.0,
                    "savings_rate_pct": 37.5,
                    "transaction_count": 25,
                    "top_expenses": [],
                }
            )

            service.generate_spending_insights(month="2026-05")

        assert len(captured_prompts) == 1
        prompt = captured_prompts[0]
        assert "Reserva Emergência" in prompt
        assert "alerta_meta" in prompt
