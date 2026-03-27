from __future__ import annotations

from dataclasses import asdict
from typing import TypedDict, cast

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserProfile,
    AuthenticatedWalletEntry,
)


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
    "AuthenticatedUserFinancialProfilePayload",
    "AuthenticatedUserIdentityPayload",
    "AuthenticatedUserInvestorProfilePayload",
    "AuthenticatedUserProductContextPayload",
    "AuthenticatedUserProfileDetailsPayload",
    "UserProfilePayload",
    "WalletEntryPayload",
    "to_authenticated_user_canonical_payload",
    "to_user_profile_payload",
    "to_wallet_entry_payload",
    "to_wallet_payload",
]
