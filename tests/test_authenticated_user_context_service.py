from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContextDependencies,
    AuthenticatedUserContextService,
)
from app.controllers.user.presenters import (
    to_user_profile_payload,
    to_wallet_payload,
)
from app.extensions.database import db
from app.graphql.authenticated_user_presenters import (
    to_authenticated_user_graphql_payload,
)
from app.models.user import User
from app.models.wallet import Wallet


def test_authenticated_user_context_service_builds_shared_profile_and_wallet(
    app,
) -> None:
    with app.app_context():
        user = User(
            name="context-user",
            email="context-user@email.com",
            password="hash",
            entitlements_version=3,
        )
        user.gender = "outro"
        user.birth_date = date(1990, 1, 2)
        user.monthly_income_net = Decimal("1234.56")
        user.net_worth = Decimal("5000.00")
        user.monthly_expenses = Decimal("789.10")
        user.initial_investment = Decimal("1500.00")
        user.monthly_investment = Decimal("200.00")
        user.investment_goal_date = date(2026, 12, 31)
        user.state_uf = "SP"
        user.occupation = "Founder"
        user.investor_profile = "entusiasta"
        user.financial_objectives = "crescimento"
        user.investor_profile_suggested = "explorador"
        user.profile_quiz_score = 18
        user.taxonomy_version = "v1"
        db.session.add(user)
        db.session.commit()

        wallet = Wallet(
            user_id=user.id,
            name="Reserva PJ",
            value=Decimal("900.00"),
            estimated_value_on_create_date=Decimal("850.00"),
            ticker=None,
            quantity=None,
            asset_class="custom",
            annual_rate=Decimal("12.5000"),
            register_date=date(2026, 3, 1),
            target_withdraw_date=date(2026, 9, 1),
            should_be_on_wallet=True,
        )
        db.session.add(wallet)
        db.session.commit()

        service = AuthenticatedUserContextService(
            dependencies=AuthenticatedUserContextDependencies(
                list_wallet_entries_by_user_id=lambda user_id: Wallet.query.filter_by(
                    user_id=user_id
                ).all(),
            )
        )

        context = service.build_context(user)
        profile_payload = to_user_profile_payload(context.profile)
        graphql_payload = to_authenticated_user_graphql_payload(context.profile)
        wallet_payload = to_wallet_payload(context.wallet_entries)

        assert context.profile.monthly_income == 1234.56
        assert context.profile.monthly_income_net == 1234.56
        assert context.profile.entitlements_version == 3
        assert profile_payload["email"] == "context-user@email.com"
        assert profile_payload["monthly_income_net"] == 1234.56
        assert graphql_payload["investor_profile_suggested"] == "explorador"
        assert len(wallet_payload) == 1
        assert wallet_payload[0]["name"] == "Reserva PJ"
        assert wallet_payload[0]["annual_rate"] == 12.5
        assert wallet_payload[0]["target_withdraw_date"] == "2026-09-01"
