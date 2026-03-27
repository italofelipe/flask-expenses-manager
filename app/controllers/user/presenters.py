from __future__ import annotations

from typing import TypedDict

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
    return {
        "id": profile.id,
        "name": profile.name,
        "email": profile.email,
        "gender": profile.gender,
        "birth_date": profile.birth_date,
        "monthly_income": profile.monthly_income,
        "monthly_income_net": profile.monthly_income_net,
        "net_worth": profile.net_worth,
        "monthly_expenses": profile.monthly_expenses,
        "initial_investment": profile.initial_investment,
        "monthly_investment": profile.monthly_investment,
        "investment_goal_date": profile.investment_goal_date,
        "state_uf": profile.state_uf,
        "occupation": profile.occupation,
        "investor_profile": profile.investor_profile,
        "financial_objectives": profile.financial_objectives,
        "investor_profile_suggested": profile.investor_profile_suggested,
        "profile_quiz_score": profile.profile_quiz_score,
        "taxonomy_version": profile.taxonomy_version,
    }


def to_wallet_entry_payload(
    wallet_entry: AuthenticatedWalletEntry,
) -> WalletEntryPayload:
    return {
        "id": wallet_entry.id,
        "name": wallet_entry.name,
        "value": wallet_entry.value,
        "estimated_value_on_create_date": (wallet_entry.estimated_value_on_create_date),
        "ticker": wallet_entry.ticker,
        "quantity": wallet_entry.quantity,
        "asset_class": wallet_entry.asset_class,
        "annual_rate": wallet_entry.annual_rate,
        "target_withdraw_date": wallet_entry.target_withdraw_date,
        "register_date": wallet_entry.register_date,
        "should_be_on_wallet": wallet_entry.should_be_on_wallet,
    }


def to_wallet_payload(
    wallet_entries: tuple[AuthenticatedWalletEntry, ...],
) -> list[WalletEntryPayload]:
    return [to_wallet_entry_payload(entry) for entry in wallet_entries]


__all__ = [
    "UserProfilePayload",
    "WalletEntryPayload",
    "to_user_profile_payload",
    "to_wallet_entry_payload",
    "to_wallet_payload",
]
