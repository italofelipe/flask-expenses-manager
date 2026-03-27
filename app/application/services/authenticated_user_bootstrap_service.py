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
from app.services.transaction_serialization import (
    TransactionPayload,
    serialize_transaction_payload,
)

DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT = 10
MAX_BOOTSTRAP_TRANSACTIONS_LIMIT = 50


@dataclass(frozen=True)
class AuthenticatedUserTransactionsPreview:
    items: tuple[TransactionPayload, ...]
    limit: int
    returned_items: int
    has_more: bool


@dataclass(frozen=True)
class AuthenticatedUserBootstrap:
    profile: AuthenticatedUserProfile
    wallet_entries: tuple[AuthenticatedWalletEntry, ...]
    transactions_preview: AuthenticatedUserTransactionsPreview


@dataclass(frozen=True)
class AuthenticatedUserBootstrapDependencies:
    list_recent_transactions_by_user_id: Callable[[UUID, int], Sequence[Transaction]]
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


def _default_dependencies() -> AuthenticatedUserBootstrapDependencies:
    return AuthenticatedUserBootstrapDependencies(
        list_recent_transactions_by_user_id=_default_list_recent_transactions_by_user_id,
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
    ) -> AuthenticatedUserBootstrap:
        normalized_limit = max(
            1,
            min(int(transactions_limit), MAX_BOOTSTRAP_TRANSACTIONS_LIMIT),
        )
        context = self._dependencies.context_service_factory().build_context(user)
        transactions_preview = self._build_transactions_preview(
            user_id=user.id,
            limit=normalized_limit,
        )
        return AuthenticatedUserBootstrap(
            profile=context.profile,
            wallet_entries=context.wallet_entries,
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


__all__ = [
    "AuthenticatedUserBootstrap",
    "AuthenticatedUserBootstrapDependencies",
    "AuthenticatedUserBootstrapService",
    "AuthenticatedUserTransactionsPreview",
    "DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT",
    "MAX_BOOTSTRAP_TRANSACTIONS_LIMIT",
]
