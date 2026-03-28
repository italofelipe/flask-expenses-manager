from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import cast
from uuid import UUID, uuid4

from app.application.services.authenticated_user_bootstrap_service import (
    DEFAULT_BOOTSTRAP_WALLET_LIMIT,
    AuthenticatedUserBootstrapDependencies,
    AuthenticatedUserBootstrapService,
)
from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContext,
    AuthenticatedUserContextDependencies,
    AuthenticatedUserContextService,
    AuthenticatedUserProfile,
    AuthenticatedWalletEntry,
)
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet


@dataclass(frozen=True)
class _FakeUser:
    id: UUID


@dataclass(frozen=True)
class _FakeTransaction:
    id: object
    title: str
    amount: Decimal
    due_date: date
    type: object
    status: object
    description: str | None = None
    observation: str | None = None
    is_recurring: bool = False
    is_installment: bool = False
    installment_count: int | None = None
    tag_id: object | None = None
    account_id: object | None = None
    credit_card_id: object | None = None
    currency: str = "BRL"
    source: str = "manual"
    external_id: str | None = None
    bank_name: str | None = None
    created_at: object | None = None
    updated_at: object | None = None
    start_date: object | None = None
    end_date: object | None = None


@dataclass(frozen=True)
class _EnumValue:
    value: str


def _build_context_service() -> AuthenticatedUserContextService:
    profile = AuthenticatedUserProfile(
        id="user-1",
        name="Italo",
        email="italo@email.com",
        gender="outro",
        birth_date="1990-01-01",
        monthly_income=1000.0,
        monthly_income_net=1000.0,
        net_worth=2000.0,
        monthly_expenses=500.0,
        initial_investment=200.0,
        monthly_investment=100.0,
        investment_goal_date="2026-12-31",
        state_uf="SP",
        occupation="Founder",
        investor_profile="conservador",
        financial_objectives="crescer",
        investor_profile_suggested="moderado",
        profile_quiz_score=8,
        taxonomy_version="2026.1",
        entitlements_version=3,
    )
    wallet_entry = AuthenticatedWalletEntry(
        id="wallet-1",
        name="Caixa",
        value=100.0,
        estimated_value_on_create_date=100.0,
        ticker=None,
        quantity=1,
        asset_class="cash",
        annual_rate=None,
        target_withdraw_date=None,
        register_date="2026-03-27",
        should_be_on_wallet=True,
    )

    class _FakeContextService(AuthenticatedUserContextService):
        def __init__(self) -> None:
            super().__init__(
                dependencies=AuthenticatedUserContextDependencies(
                    list_wallet_entries_by_user_id=lambda _user_id: []
                )
            )

        def build_profile(self, _user: User) -> AuthenticatedUserProfile:
            return profile

        def build_wallet_entries_snapshot(
            self, _wallet_entries: Sequence[Wallet]
        ) -> tuple[AuthenticatedWalletEntry, ...]:
            return (wallet_entry,)

        def build_context(self, _user: User) -> AuthenticatedUserContext:
            return AuthenticatedUserContext(
                profile=profile, wallet_entries=(wallet_entry,)
            )

    return cast(AuthenticatedUserContextService, _FakeContextService())


def test_authenticated_user_bootstrap_service_builds_preview_and_wallet() -> None:
    fake_user = _FakeUser(id=uuid4())
    transactions = [
        _FakeTransaction(
            id=uuid4(),
            title=f"Transaction {index}",
            amount=Decimal("10.00"),
            due_date=date(2026, 3, index + 1),
            type=_EnumValue("expense"),
            status=_EnumValue("pending"),
        )
        for index in range(3)
    ]

    def _list_recent_transactions(
        _user_id: UUID,
        _limit_plus_one: int,
    ) -> list[Transaction]:
        return cast(list[Transaction], list(transactions))

    def _list_wallet_preview_entries(
        _user_id: UUID,
        _limit: int,
    ) -> list[Wallet]:
        return []

    service = AuthenticatedUserBootstrapService(
        dependencies=AuthenticatedUserBootstrapDependencies(
            list_recent_transactions_by_user_id=_list_recent_transactions,
            list_wallet_preview_entries_by_user_id=_list_wallet_preview_entries,
            count_wallet_entries_by_user_id=lambda _user_id: 1,
            context_service_factory=_build_context_service,
        )
    )

    bootstrap = service.build_bootstrap(cast(User, fake_user), transactions_limit=2)

    assert bootstrap.profile.email == "italo@email.com"
    assert len(bootstrap.wallet_preview.items) == 1
    assert bootstrap.wallet_preview.total == 1
    assert bootstrap.wallet_preview.limit == DEFAULT_BOOTSTRAP_WALLET_LIMIT
    assert bootstrap.wallet_preview.returned_items == 1
    assert bootstrap.wallet_preview.has_more is False
    assert bootstrap.transactions_preview.limit == 2
    assert bootstrap.transactions_preview.returned_items == 2
    assert bootstrap.transactions_preview.has_more is True
    assert bootstrap.transactions_preview.items[0]["title"] == "Transaction 0"
