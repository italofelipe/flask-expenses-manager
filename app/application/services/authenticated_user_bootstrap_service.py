from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import cast
from uuid import UUID

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContextService,
    AuthenticatedUserProfile,
    AuthenticatedWalletEntry,
)
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.services.transaction_serialization import (
    TransactionPayload,
    serialize_transaction_payload,
)

DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT = 10
MAX_BOOTSTRAP_TRANSACTIONS_LIMIT = 50
DEFAULT_BOOTSTRAP_WALLET_LIMIT = 5


@dataclass(frozen=True)
class AuthenticatedUserTransactionsPreview:
    items: tuple[TransactionPayload, ...]
    limit: int
    returned_items: int
    has_more: bool


@dataclass(frozen=True)
class AuthenticatedUserWalletPreview:
    items: tuple[AuthenticatedWalletEntry, ...]
    total: int
    limit: int
    returned_items: int
    has_more: bool


@dataclass(frozen=True)
class AuthenticatedUserBootstrap:
    profile: AuthenticatedUserProfile
    wallet_preview: AuthenticatedUserWalletPreview
    transactions_preview: AuthenticatedUserTransactionsPreview


@dataclass(frozen=True)
class AuthenticatedUserBootstrapDependencies:
    list_recent_transactions_by_user_id: Callable[[UUID, int], Sequence[Transaction]]
    list_wallet_preview_entries_by_user_id: Callable[[UUID, int], Sequence[Wallet]]
    count_wallet_entries_by_user_id: Callable[[UUID], int]
    context_service_factory: Callable[[], AuthenticatedUserContextService]


def _default_list_recent_transactions_by_user_id(
    user_id: UUID,
    limit_plus_one: int,
) -> Sequence[Transaction]:
    return cast(
        Sequence[Transaction],
        Transaction.query.filter_by(user_id=user_id, deleted=False)
        .order_by(Transaction.due_date.desc())
        .limit(limit_plus_one)
        .all(),
    )


def _default_list_wallet_preview_entries_by_user_id(
    user_id: UUID,
    limit: int,
) -> Sequence[Wallet]:
    return cast(
        Sequence[Wallet],
        Wallet.query.filter_by(user_id=user_id)
        .order_by(Wallet.register_date.desc(), Wallet.created_at.desc())
        .limit(limit)
        .all(),
    )


def _default_count_wallet_entries_by_user_id(user_id: UUID) -> int:
    return int(Wallet.query.filter_by(user_id=user_id).count())


def _default_dependencies() -> AuthenticatedUserBootstrapDependencies:
    return AuthenticatedUserBootstrapDependencies(
        list_recent_transactions_by_user_id=_default_list_recent_transactions_by_user_id,
        list_wallet_preview_entries_by_user_id=(
            _default_list_wallet_preview_entries_by_user_id
        ),
        count_wallet_entries_by_user_id=_default_count_wallet_entries_by_user_id,
        context_service_factory=AuthenticatedUserContextService.with_defaults,
    )


class AuthenticatedUserBootstrapService:
    def __init__(
        self,
        *,
        dependencies: AuthenticatedUserBootstrapDependencies,
    ) -> None:
        self._dependencies = dependencies

    @classmethod
    def with_defaults(cls) -> AuthenticatedUserBootstrapService:
        return cls(dependencies=_default_dependencies())

    def build_bootstrap(
        self,
        user: User,
        *,
        transactions_limit: int = DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT,
        wallet_limit: int = DEFAULT_BOOTSTRAP_WALLET_LIMIT,
    ) -> AuthenticatedUserBootstrap:
        normalized_transactions_limit = max(
            1,
            min(int(transactions_limit), MAX_BOOTSTRAP_TRANSACTIONS_LIMIT),
        )
        normalized_wallet_limit = max(1, int(wallet_limit))
        context_service = self._dependencies.context_service_factory()
        transactions_preview = self._build_transactions_preview(
            user_id=user.id,
            limit=normalized_transactions_limit,
        )
        wallet_preview = self._build_wallet_preview(
            context_service=context_service,
            user_id=user.id,
            limit=normalized_wallet_limit,
        )
        return AuthenticatedUserBootstrap(
            profile=context_service.build_profile(user),
            wallet_preview=wallet_preview,
            transactions_preview=transactions_preview,
        )

    def _build_transactions_preview(
        self,
        *,
        user_id: UUID,
        limit: int,
    ) -> AuthenticatedUserTransactionsPreview:
        recent_transactions = self._dependencies.list_recent_transactions_by_user_id(
            user_id,
            limit + 1,
        )
        visible_items = tuple(
            serialize_transaction_payload(transaction)
            for transaction in recent_transactions[:limit]
        )
        return AuthenticatedUserTransactionsPreview(
            items=visible_items,
            limit=limit,
            returned_items=len(visible_items),
            has_more=len(recent_transactions) > limit,
        )

    def _build_wallet_preview(
        self,
        *,
        context_service: AuthenticatedUserContextService,
        user_id: UUID,
        limit: int,
    ) -> AuthenticatedUserWalletPreview:
        wallet_entries = self._dependencies.list_wallet_preview_entries_by_user_id(
            user_id,
            limit,
        )
        total_entries = self._dependencies.count_wallet_entries_by_user_id(user_id)
        visible_items = context_service.build_wallet_entries_snapshot(wallet_entries)
        return AuthenticatedUserWalletPreview(
            items=visible_items,
            total=total_entries,
            limit=limit,
            returned_items=len(visible_items),
            has_more=total_entries > len(visible_items),
        )


__all__ = [
    "AuthenticatedUserBootstrap",
    "AuthenticatedUserBootstrapDependencies",
    "AuthenticatedUserBootstrapService",
    "AuthenticatedUserTransactionsPreview",
    "AuthenticatedUserWalletPreview",
    "DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT",
    "DEFAULT_BOOTSTRAP_WALLET_LIMIT",
    "MAX_BOOTSTRAP_TRANSACTIONS_LIMIT",
]
