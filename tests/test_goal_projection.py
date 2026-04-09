"""Tests for GoalProjectionService and related application/controller wiring.

Coverage:
  - Pure math helpers: _months_to_reach_goal_compound, _suggested_monthly_contribution
  - compute_portfolio_monthly_return_rate (mocked wallet queries)
  - GoalProjectionService.project + serialize
  - GoalApplicationService.get_goal_projection
  - GET /goals/<goal_id>/projection HTTP endpoint (contract + error cases)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.services.goal_projection_service import (
    GoalProjectionService,
    _months_to_reach_goal_compound,
    _suggested_monthly_contribution,
    compute_portfolio_monthly_return_rate,
)

# ---------------------------------------------------------------------------
# Pure math helpers
# ---------------------------------------------------------------------------


class TestMonthsToReachGoalCompound:
    def test_already_reached_returns_zero(self) -> None:
        result = _months_to_reach_goal_compound(
            current=Decimal("5000"),
            target=Decimal("3000"),
            monthly_contribution=Decimal("500"),
            monthly_rate=Decimal("0.01"),
        )
        assert result == 0

    def test_exactly_at_target_returns_zero(self) -> None:
        result = _months_to_reach_goal_compound(
            current=Decimal("5000"),
            target=Decimal("5000"),
            monthly_contribution=Decimal("0"),
            monthly_rate=Decimal("0"),
        )
        assert result == 0

    def test_zero_rate_falls_back_to_linear(self) -> None:
        # 5000 remaining / 500 per month = 10 months
        result = _months_to_reach_goal_compound(
            current=Decimal("0"),
            target=Decimal("5000"),
            monthly_contribution=Decimal("500"),
            monthly_rate=Decimal("0"),
        )
        assert result == 10

    def test_zero_rate_zero_contribution_returns_none(self) -> None:
        result = _months_to_reach_goal_compound(
            current=Decimal("0"),
            target=Decimal("5000"),
            monthly_contribution=Decimal("0"),
            monthly_rate=Decimal("0"),
        )
        assert result is None

    def test_compound_interest_gives_fewer_months_than_linear(self) -> None:
        # With 1% monthly rate and 500 contribution, reaching 10000 from 0
        # should be faster than simple 10000/500 = 20 months
        compound = _months_to_reach_goal_compound(
            current=Decimal("0"),
            target=Decimal("10000"),
            monthly_contribution=Decimal("500"),
            monthly_rate=Decimal("0.01"),
        )
        linear = 20  # 10000/500
        assert compound is not None
        assert compound < linear

    def test_exceeds_max_projection_months_returns_none(self) -> None:
        # Near-zero contribution and tiny rate on a huge target
        result = _months_to_reach_goal_compound(
            current=Decimal("0"),
            target=Decimal("10000000"),
            monthly_contribution=Decimal("1"),
            monthly_rate=Decimal("0.000001"),
        )
        assert result is None

    def test_positive_return_rate_only_reaches_goal(self) -> None:
        # Even with zero contribution, if there's return and current > 0,
        # the FV will eventually exceed target
        result = _months_to_reach_goal_compound(
            current=Decimal("5000"),
            target=Decimal("6000"),
            monthly_contribution=Decimal("0"),
            monthly_rate=Decimal("0.01"),
        )
        assert result is not None
        assert result > 0


class TestSuggestedMonthlyContribution:
    def test_already_reached_returns_zero(self) -> None:
        result = _suggested_monthly_contribution(
            current=Decimal("10000"),
            target=Decimal("8000"),
            months_to_deadline=12,
            monthly_rate=Decimal("0.01"),
        )
        assert result == Decimal("0")

    def test_zero_months_returns_remaining(self) -> None:
        result = _suggested_monthly_contribution(
            current=Decimal("0"),
            target=Decimal("5000"),
            months_to_deadline=0,
            monthly_rate=Decimal("0.01"),
        )
        assert result == Decimal("5000")

    def test_zero_rate_simple_division(self) -> None:
        result = _suggested_monthly_contribution(
            current=Decimal("0"),
            target=Decimal("12000"),
            months_to_deadline=12,
            monthly_rate=Decimal("0"),
        )
        assert result == Decimal("1000.00")

    def test_positive_rate_yields_lower_contribution_than_linear(self) -> None:
        # With compound returns, you need to contribute less than simple division
        compound = _suggested_monthly_contribution(
            current=Decimal("0"),
            target=Decimal("12000"),
            months_to_deadline=12,
            monthly_rate=Decimal("0.01"),
        )
        simple = Decimal("12000") / Decimal("12")
        assert compound < simple

    def test_result_is_non_negative(self) -> None:
        result = _suggested_monthly_contribution(
            current=Decimal("11000"),
            target=Decimal("12000"),
            months_to_deadline=24,
            monthly_rate=Decimal("0.01"),
        )
        assert result >= Decimal("0")


# ---------------------------------------------------------------------------
# Portfolio rate
# ---------------------------------------------------------------------------


class TestComputePortfolioMonthlyReturnRate:
    def test_no_wallets_returns_zero(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        assert compute_portfolio_monthly_return_rate(uuid4()) == Decimal("0")

    def test_wallets_with_zero_value_returns_zero(self, monkeypatch) -> None:
        class _W:
            value = Decimal("0")
            annual_rate = Decimal("10")

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_W()],
        )
        assert compute_portfolio_monthly_return_rate(uuid4()) == Decimal("0")

    def test_wallets_with_zero_annual_rate_returns_zero(self, monkeypatch) -> None:
        class _W:
            value = Decimal("1000")
            annual_rate = Decimal("0")

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_W()],
        )
        assert compute_portfolio_monthly_return_rate(uuid4()) == Decimal("0")

    def test_single_wallet_converts_to_monthly_rate(self, monkeypatch) -> None:
        class _W:
            value = Decimal("1000")
            annual_rate = Decimal("12")  # 12% annual

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_W()],
        )
        rate = compute_portfolio_monthly_return_rate(uuid4())
        # (1 + 0.12)^(1/12) - 1 ≈ 0.009489
        assert Decimal("0.009") < rate < Decimal("0.010")

    def test_value_weighted_average(self, monkeypatch) -> None:
        class _W1:
            value = Decimal("1000")
            annual_rate = Decimal("12")

        class _W2:
            value = Decimal("3000")
            annual_rate = Decimal("24")

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_W1(), _W2()],
        )
        rate = compute_portfolio_monthly_return_rate(uuid4())
        # Blended annual = (1000*12 + 3000*24) / 4000 = 21% → monthly ≈ 0.01600
        assert Decimal("0.015") < rate < Decimal("0.018")

    def test_none_values_ignored(self, monkeypatch) -> None:
        class _W1:
            value = None
            annual_rate = Decimal("12")

        class _W2:
            value = Decimal("2000")
            annual_rate = Decimal("12")

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_W1(), _W2()],
        )
        rate = compute_portfolio_monthly_return_rate(uuid4())
        assert rate > Decimal("0")


# ---------------------------------------------------------------------------
# GoalProjectionService.project
# ---------------------------------------------------------------------------


def _make_service(
    monthly_contribution: str = "500",
    monthly_rate: str | None = None,
    today: date | None = None,
) -> GoalProjectionService:
    def _rate_provider(_uid: UUID) -> Decimal:
        return Decimal(monthly_rate) if monthly_rate is not None else Decimal("0.01")

    return GoalProjectionService(
        monthly_contribution=Decimal(monthly_contribution),
        today_provider=lambda: today or date(2025, 1, 1),
        portfolio_rate_provider=_rate_provider,
    )


class TestGoalProjectionServiceProject:
    def test_already_reached_goal(self) -> None:
        svc = _make_service()
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("10000"),
            target_amount=Decimal("8000"),
            target_date=None,
        )
        assert proj.months_to_completion == 0
        assert proj.remaining_amount == Decimal("0.00")

    def test_no_deadline_no_on_track(self) -> None:
        svc = _make_service()
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("1000"),
            target_amount=Decimal("10000"),
            target_date=None,
        )
        assert proj.on_track is False
        assert proj.months_until_deadline is None
        assert proj.suggested_monthly_contribution is None

    def test_on_track_when_projection_within_deadline(self) -> None:
        svc = _make_service(monthly_contribution="1000")
        # With 1% monthly rate and 1000/month starting at 1000 toward 10000:
        # should finish well within 24 months
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("1000"),
            target_amount=Decimal("10000"),
            target_date=date(2027, 1, 1),  # ~24 months from today (2025-01-01)
        )
        assert proj.on_track is True
        assert proj.suggested_monthly_contribution is None

    def test_not_on_track_provides_suggested_contribution(self) -> None:
        # With 100/month, reaching 10000 from 1000 will take > 3 months
        svc = _make_service(monthly_contribution="100")
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("1000"),
            target_amount=Decimal("10000"),
            target_date=date(2025, 4, 1),  # only 3 months away
        )
        assert proj.on_track is False
        assert proj.suggested_monthly_contribution is not None
        assert proj.suggested_monthly_contribution > Decimal("100")

    def test_projected_completion_date_set(self) -> None:
        svc = _make_service(monthly_contribution="500", today=date(2025, 1, 1))
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("5000"),
            target_date=None,
        )
        assert proj.projected_completion_date is not None
        assert proj.projected_completion_date > date(2025, 1, 1)

    def test_annual_rate_pct_computed_from_monthly(self) -> None:
        svc = _make_service(monthly_rate="0.01")
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("1000"),
            target_date=None,
        )
        # (1.01)^12 - 1 ≈ 12.68%
        assert Decimal("12") < proj.portfolio_annual_return_rate_pct < Decimal("14")

    def test_zero_rate_zero_contribution_returns_none_months(self) -> None:
        svc = _make_service(monthly_contribution="0", monthly_rate="0")
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("1000"),
            target_date=None,
        )
        assert proj.months_to_completion is None
        assert proj.projected_completion_date is None

    def test_past_deadline_months_until_deadline_is_zero(self) -> None:
        svc = _make_service(today=date(2025, 6, 1))
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("5000"),
            target_date=date(2025, 1, 1),  # in the past
        )
        assert proj.months_until_deadline == 0


class TestGoalProjectionServiceSerialize:
    def test_serialize_returns_string_fields(self) -> None:
        svc = _make_service()
        goal_id = uuid4()
        proj = svc.project(
            goal_id=goal_id,
            user_id=uuid4(),
            current_amount=Decimal("1000"),
            target_amount=Decimal("5000"),
            target_date=date(2026, 12, 31),
        )
        data = svc.serialize(proj)
        assert data["goal_id"] == str(goal_id)
        assert isinstance(data["current_amount"], str)
        assert isinstance(data["target_amount"], str)
        assert isinstance(data["remaining_amount"], str)
        assert isinstance(data["monthly_contribution"], str)
        assert isinstance(data["portfolio_monthly_return_rate"], str)
        assert isinstance(data["portfolio_annual_return_rate_pct"], str)
        assert isinstance(data["on_track"], bool)

    def test_serialize_none_fields_as_none(self) -> None:
        svc = _make_service(monthly_contribution="0", monthly_rate="0")
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("1000"),
            target_date=None,
        )
        data = svc.serialize(proj)
        assert data["months_to_completion"] is None
        assert data["projected_completion_date"] is None
        assert data["months_until_deadline"] is None
        assert data["suggested_monthly_contribution"] is None

    def test_serialize_completion_date_as_iso(self) -> None:
        svc = _make_service(monthly_contribution="500", today=date(2025, 1, 1))
        proj = svc.project(
            goal_id=uuid4(),
            user_id=uuid4(),
            current_amount=Decimal("0"),
            target_amount=Decimal("1000"),
            target_date=None,
        )
        data = svc.serialize(proj)
        if data["projected_completion_date"] is not None:
            # Must be ISO-format string
            date.fromisoformat(str(data["projected_completion_date"]))


# ---------------------------------------------------------------------------
# GoalApplicationService.get_goal_projection
# ---------------------------------------------------------------------------


class _FakeGoalForProjection:
    def __init__(self) -> None:
        self.id = uuid4()
        self.target_amount = Decimal("10000")
        self.current_amount = Decimal("2000")
        self.target_date = date(2027, 12, 31)


class _FakeGoalServiceForProjection:
    def __init__(self, user_id: UUID) -> None:
        self._goal = _FakeGoalForProjection()

    def get_goal(self, goal_id: UUID) -> _FakeGoalForProjection:
        return self._goal

    def serialize(self, goal: Any) -> dict[str, Any]:
        return {"id": str(goal.id), "title": "Test Goal"}


class _FakeUserWithInvestment:
    monthly_investment = Decimal("800")


def _build_projection_app_service(
    *,
    rate_provider: Any = None,
    today_provider: Any = None,
) -> Any:
    from app.application.services.goal_application_service import GoalApplicationService
    from app.services.goal_planning_service import GoalPlanningService

    svc = GoalApplicationService(
        user_id=uuid4(),
        goal_service_factory=_FakeGoalServiceForProjection,
        goal_planning_service_factory=GoalPlanningService,
        get_user_by_id=lambda _uid: _FakeUserWithInvestment(),
    )
    return svc


class TestGoalApplicationServiceGetGoalProjection:
    def test_returns_goal_and_projection_keys(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        svc = _build_projection_app_service()
        result = svc.get_goal_projection(uuid4())
        assert "goal" in result
        assert "projection" in result

    def test_projection_contains_required_fields(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        svc = _build_projection_app_service()
        proj = svc.get_goal_projection(uuid4())["projection"]
        for field in (
            "goal_id",
            "current_amount",
            "target_amount",
            "remaining_amount",
            "monthly_contribution",
            "portfolio_monthly_return_rate",
            "portfolio_annual_return_rate_pct",
            "months_to_completion",
            "projected_completion_date",
            "on_track",
            "months_until_deadline",
            "suggested_monthly_contribution",
        ):
            assert field in proj, f"Missing field: {field}"

    def test_monthly_contribution_matches_user_investment(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        svc = _build_projection_app_service()
        proj = svc.get_goal_projection(uuid4())["projection"]
        assert proj["monthly_contribution"] == "800.00"

    def test_zero_contribution_when_user_has_none(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        from app.application.services.goal_application_service import (
            GoalApplicationService,
        )
        from app.services.goal_planning_service import GoalPlanningService

        class _UserNoInvestment:
            monthly_investment = None

        svc = GoalApplicationService(
            user_id=uuid4(),
            goal_service_factory=_FakeGoalServiceForProjection,
            goal_planning_service_factory=GoalPlanningService,
            get_user_by_id=lambda _uid: _UserNoInvestment(),
        )
        proj = svc.get_goal_projection(uuid4())["projection"]
        assert proj["monthly_contribution"] == "0.00"


# ---------------------------------------------------------------------------
# HTTP endpoint: GET /goals/<goal_id>/projection
# ---------------------------------------------------------------------------


def _register_and_login(client: Any, prefix: str = "proj") -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"

    r = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert r.status_code == 201

    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200
    return str(r.get_json()["token"])


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_goal(client: Any, token: str) -> str:
    r = client.post(
        "/goals",
        headers=_auth(token),
        json={
            "title": "Projeção Teste",
            "target_amount": "10000.00",
            "current_amount": "1000.00",
            "target_date": "2028-12-31",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    # Support both legacy (body["goal"]) and v2 (body["data"]["goal"]) shapes
    if "goal" in body:
        return str(body["goal"]["id"])
    return str(body["data"]["goal"]["id"])


class TestGoalProjectionEndpoint:
    def test_projection_returns_200_and_required_keys(
        self, client, monkeypatch
    ) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        token = _register_and_login(client, "proj-ok")
        goal_id = _create_goal(client, token)

        response = client.get(f"/goals/{goal_id}/projection", headers=_auth(token))
        assert response.status_code == 200

        body = response.get_json()
        # Legacy contract (no X-API-Contract header)
        assert "goal" in body or (
            body.get("success") and "goal" in body.get("data", {})
        )

    def test_projection_v2_contract(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        token = _register_and_login(client, "proj-v2")
        goal_id = _create_goal(client, token)

        response = client.get(
            f"/goals/{goal_id}/projection",
            headers={**_auth(token), "X-API-Contract": "v2"},
        )
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        data = body["data"]
        assert "goal" in data
        assert "projection" in data

        proj = data["projection"]
        assert "goal_id" in proj
        assert "months_to_completion" in proj
        assert "on_track" in proj
        assert "monthly_contribution" in proj
        assert "portfolio_monthly_return_rate" in proj

    def test_projection_requires_auth(self, client) -> None:
        fake_id = str(uuid4())
        response = client.get(f"/goals/{fake_id}/projection")
        assert response.status_code == 401

    def test_projection_returns_404_for_unknown_goal(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        token = _register_and_login(client, "proj-404")
        fake_id = str(uuid4())
        response = client.get(f"/goals/{fake_id}/projection", headers=_auth(token))
        assert response.status_code == 404

    def test_projection_other_user_cannot_access(self, client, monkeypatch) -> None:
        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [],
        )
        owner_token = _register_and_login(client, "proj-owner")
        other_token = _register_and_login(client, "proj-other")
        goal_id = _create_goal(client, owner_token)

        response = client.get(
            f"/goals/{goal_id}/projection",
            headers=_auth(other_token),
        )
        # Should be 403 or 404 — the goal belongs to another user
        assert response.status_code in (403, 404)

    def test_projection_reflects_portfolio_rate(self, client, monkeypatch) -> None:
        """With a non-zero portfolio rate, annual_rate_pct should be > 0."""

        class _MockWallet:
            value = Decimal("10000")
            annual_rate = Decimal("12")

        monkeypatch.setattr(
            "app.services.goal_projection_service._fetch_user_wallets",
            lambda _uid: [_MockWallet()],
        )
        token = _register_and_login(client, "proj-rate")
        goal_id = _create_goal(client, token)

        response = client.get(
            f"/goals/{goal_id}/projection",
            headers={**_auth(token), "X-API-Contract": "v2"},
        )
        assert response.status_code == 200
        proj = response.get_json()["data"]["projection"]
        assert Decimal(proj["portfolio_annual_return_rate_pct"]) > Decimal("0")
        assert Decimal(proj["portfolio_monthly_return_rate"]) > Decimal("0")
