from __future__ import annotations

from decimal import Decimal

from app.extensions.database import db
from app.models.goal import Goal
from app.models.user import User


def _create_user() -> User:
    user = User(
        name="goal-model-user",
        email="goal-model-user@email.com",
        password="StrongPass@123",
    )
    db.session.add(user)
    db.session.commit()
    return user


def test_goal_model_persists_with_defaults(app) -> None:
    with app.app_context():
        user = _create_user()
        goal = Goal(
            user_id=user.id,
            title="Reserva de emergência",
            target_amount=Decimal("10000.00"),
        )
        db.session.add(goal)
        db.session.commit()

        stored = Goal.query.filter_by(id=goal.id).first()
        assert stored is not None
        assert stored.title == "Reserva de emergência"
        assert Decimal(str(stored.target_amount)) == Decimal("10000.00")
        assert Decimal(str(stored.current_amount)) == Decimal("0.00")
        assert stored.priority == 3
        assert stored.status == "active"
        assert stored.created_at is not None
        assert stored.updated_at is not None


def test_goal_model_relationship_with_user(app) -> None:
    with app.app_context():
        user = _create_user()
        goal = Goal(
            user_id=user.id,
            title="Aposentadoria",
            target_amount=Decimal("500000.00"),
            current_amount=Decimal("125000.00"),
            priority=1,
        )
        db.session.add(goal)
        db.session.commit()

        refreshed = User.query.filter_by(id=user.id).first()
        assert refreshed is not None
        assert len(refreshed.goals) == 1
        assert refreshed.goals[0].title == "Aposentadoria"
