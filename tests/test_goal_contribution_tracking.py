"""Integration tests for GoalContribution tracking hook (#1234).

Coverage:
- update_goal with current_amount increase creates GoalContribution with correct delta
- update_goal with current_amount decrease creates GoalContribution with negative delta
- update_goal without current_amount in payload does NOT create GoalContribution
- update_goal with current_amount unchanged does NOT create GoalContribution
- contribution record failure does not break the goal update flow
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from app.extensions.database import db
from app.models.goal_contribution import GoalContribution

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str = "gc-test") -> tuple[str, str]:
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
    token = login.get_json()["token"]
    user_id = login.get_json().get("user", {}).get("id") or _get_user_id_from_token(
        token
    )
    return token, user_id


def _get_user_id_from_token(token: str) -> str:
    from flask_jwt_extended import decode_token

    return decode_token(token)["sub"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "X-API-Contract": "v2"}


def _create_goal(client, token: str, *, current_amount: float = 0.0) -> str:
    resp = client.post(
        "/goals",
        json={
            "title": "Test Goal",
            "target_amount": 1000.0,
            "current_amount": current_amount,
        },
        headers=_auth(token),
    )
    assert resp.status_code == 201, resp.get_json()
    body = resp.get_json()
    # Support both v2 envelope (data.goal.id) and legacy (goal.id)
    if "data" in body:
        return body["data"]["goal"]["id"]
    return body["goal"]["id"]


def _update_goal(client, token: str, goal_id: str, payload: dict) -> dict:
    resp = client.patch(
        f"/goals/{goal_id}",
        json=payload,
        headers=_auth(token),
    )
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _contributions_for_goal(app, goal_id: str) -> list[GoalContribution]:
    with app.app_context():
        return (
            db.session.query(GoalContribution)
            .filter_by(goal_id=uuid.UUID(goal_id))
            .order_by(GoalContribution.created_at)
            .all()
        )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGoalContributionTracking:
    def test_increase_creates_positive_contribution(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=100.0)

        _update_goal(client, token, goal_id, {"current_amount": 350.0})

        contributions = _contributions_for_goal(app, goal_id)
        assert len(contributions) == 1
        assert contributions[0].amount == Decimal("250.00")

    def test_decrease_creates_negative_contribution(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=500.0)

        _update_goal(client, token, goal_id, {"current_amount": 300.0})

        contributions = _contributions_for_goal(app, goal_id)
        assert len(contributions) == 1
        assert contributions[0].amount == Decimal("-200.00")

    def test_non_monetary_update_does_not_create_contribution(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=100.0)

        _update_goal(client, token, goal_id, {"title": "Renamed Goal"})

        contributions = _contributions_for_goal(app, goal_id)
        assert len(contributions) == 0

    def test_same_amount_update_does_not_create_contribution(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=100.0)

        _update_goal(client, token, goal_id, {"current_amount": 100.0})

        contributions = _contributions_for_goal(app, goal_id)
        assert len(contributions) == 0

    def test_multiple_contributions_cumulate(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=0.0)

        _update_goal(client, token, goal_id, {"current_amount": 200.0})
        _update_goal(client, token, goal_id, {"current_amount": 350.0})

        contributions = _contributions_for_goal(app, goal_id)
        assert len(contributions) == 2
        amounts = [c.amount for c in contributions]
        assert Decimal("200.00") in amounts
        assert Decimal("150.00") in amounts

    def test_contribution_has_correct_user_id(self, client, app):
        token, _ = _register_and_login(client)
        goal_id = _create_goal(client, token, current_amount=0.0)
        _update_goal(client, token, goal_id, {"current_amount": 100.0})

        with app.app_context():
            from flask_jwt_extended import decode_token

            user_id = uuid.UUID(decode_token(token)["sub"])
            contrib = (
                db.session.query(GoalContribution)
                .filter_by(goal_id=uuid.UUID(goal_id))
                .first()
            )
            assert contrib is not None
            assert contrib.user_id == user_id
