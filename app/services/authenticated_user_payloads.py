from __future__ import annotations

from dataclasses import asdict
from typing import TypedDict, cast

from app.application.services.authenticated_user_bootstrap_service import (
    AuthenticatedUserBootstrap,
    AuthenticatedUserTransactionsPreview,
)
from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserProfile,
    AuthenticatedWalletEntry,
)
from app.services.transaction_serialization import TransactionPayload


class UserProfilePayload(TypedDict):
    id: str
    name: str
    email: str
    gender: str | None
    birth_date: str | None
    monthly_income: float | None
    monthly_income_net: float | None
    net_worth: float | None
    monthly_expenses: float | None
    initial_investment: float | None
    monthly_investment: float | None
    investment_goal_date: str | None
    state_uf: str | None
    occupation: str | None
    investor_profile: str | None
    financial_objectives: str | None
    investor_profile_suggested: str | None
    profile_quiz_score: int | None
    taxonomy_version: str | None


class AuthenticatedUserIdentityPayload(TypedDict):
    id: str
    name: str
    email: str


class AuthenticatedUserProfileDetailsPayload(TypedDict):
    gender: str | None
    birth_date: str | None
    state_uf: str | None
    occupation: str | None


class AuthenticatedUserFinancialProfilePayload(TypedDict):
    monthly_income_net: float | None
    monthly_expenses: float | None
    net_worth: float | None
    initial_investment: float | None
    monthly_investment: float | None
    investment_goal_date: str | None


class AuthenticatedUserInvestorProfilePayload(TypedDict):
    declared: str | None
    suggested: str | None
    quiz_score: int | None
    taxonomy_version: str | None
    financial_objectives: str | None


class AuthenticatedUserProductContextPayload(TypedDict):
    entitlements_version: int


class AuthenticatedUserCanonicalPayload(TypedDict):
    identity: AuthenticatedUserIdentityPayload
    profile: AuthenticatedUserProfileDetailsPayload
    financial_profile: AuthenticatedUserFinancialProfilePayload
    investor_profile: AuthenticatedUserInvestorProfilePayload
    product_context: AuthenticatedUserProductContextPayload


class AuthenticatedUserTransactionsPreviewPayload(TypedDict):
    items: list[TransactionPayload]
    returned_items: int
    limit: int
    has_more: bool


class AuthenticatedUserBootstrapWalletPayload(TypedDict):
    items: list[WalletEntryPayload]
    total: int


class AuthenticatedUserBootstrapPayload(TypedDict):
    user: AuthenticatedUserCanonicalPayload
    transactions_preview: AuthenticatedUserTransactionsPreviewPayload
    wallet: AuthenticatedUserBootstrapWalletPayload


class WalletEntryPayload(TypedDict):
    id: str
    name: str
    value: float | None
    estimated_value_on_create_date: float | None
    ticker: str | None
    quantity: int | None
    asset_class: str
    annual_rate: float | None
    target_withdraw_date: str | None
    register_date: str
    should_be_on_wallet: bool


def to_user_profile_payload(profile: AuthenticatedUserProfile) -> UserProfilePayload:
    payload = asdict(profile)
    payload.pop("entitlements_version", None)
    return cast(UserProfilePayload, payload)


def to_authenticated_user_canonical_payload(
    profile: AuthenticatedUserProfile,
) -> AuthenticatedUserCanonicalPayload:
    return {
        "identity": {
            "id": profile.id,
            "name": profile.name,
            "email": profile.email,
        },
        "profile": {
            "gender": profile.gender,
            "birth_date": profile.birth_date,
            "state_uf": profile.state_uf,
            "occupation": profile.occupation,
        },
        "financial_profile": {
            "monthly_income_net": profile.monthly_income_net,
            "monthly_expenses": profile.monthly_expenses,
            "net_worth": profile.net_worth,
            "initial_investment": profile.initial_investment,
            "monthly_investment": profile.monthly_investment,
            "investment_goal_date": profile.investment_goal_date,
        },
        "investor_profile": {
            "declared": profile.investor_profile,
            "suggested": profile.investor_profile_suggested,
            "quiz_score": profile.profile_quiz_score,
            "taxonomy_version": profile.taxonomy_version,
            "financial_objectives": profile.financial_objectives,
        },
        "product_context": {
            "entitlements_version": profile.entitlements_version,
        },
    }


def to_transactions_preview_payload(
    preview: AuthenticatedUserTransactionsPreview,
) -> AuthenticatedUserTransactionsPreviewPayload:
    return {
        "items": list(preview.items),
        "returned_items": preview.returned_items,
        "limit": preview.limit,
        "has_more": preview.has_more,
    }


def to_authenticated_user_bootstrap_payload(
    bootstrap: AuthenticatedUserBootstrap,
) -> AuthenticatedUserBootstrapPayload:
    wallet_items = to_wallet_payload(bootstrap.wallet_entries)
    return {
        "user": to_authenticated_user_canonical_payload(bootstrap.profile),
        "transactions_preview": to_transactions_preview_payload(
            bootstrap.transactions_preview
        ),
        "wallet": {
            "items": wallet_items,
            "total": len(wallet_items),
        },
    }


def to_wallet_entry_payload(
    wallet_entry: AuthenticatedWalletEntry,
) -> WalletEntryPayload:
    return cast(WalletEntryPayload, asdict(wallet_entry))


def to_wallet_payload(
    wallet_entries: tuple[AuthenticatedWalletEntry, ...],
) -> list[WalletEntryPayload]:
    return [to_wallet_entry_payload(entry) for entry in wallet_entries]


__all__ = [
    "AuthenticatedUserCanonicalPayload",
    "AuthenticatedUserBootstrapPayload",
    "AuthenticatedUserBootstrapWalletPayload",
    "AuthenticatedUserFinancialProfilePayload",
    "AuthenticatedUserIdentityPayload",
    "AuthenticatedUserInvestorProfilePayload",
    "AuthenticatedUserProductContextPayload",
    "AuthenticatedUserProfileDetailsPayload",
    "AuthenticatedUserTransactionsPreviewPayload",
    "UserProfilePayload",
    "WalletEntryPayload",
    "to_authenticated_user_bootstrap_payload",
    "to_authenticated_user_canonical_payload",
    "to_transactions_preview_payload",
    "to_user_profile_payload",
    "to_wallet_entry_payload",
    "to_wallet_payload",
]
