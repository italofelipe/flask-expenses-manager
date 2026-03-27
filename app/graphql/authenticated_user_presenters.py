from __future__ import annotations

from typing import TypedDict

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserProfile,
)
from app.graphql.types import UserType


class AuthenticatedUserGraphQLPayload(TypedDict):
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


def to_authenticated_user_graphql_payload(
    profile: AuthenticatedUserProfile,
) -> AuthenticatedUserGraphQLPayload:
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


def to_authenticated_user_type(profile: AuthenticatedUserProfile) -> UserType:
    return UserType(**to_authenticated_user_graphql_payload(profile))


__all__ = [
    "AuthenticatedUserGraphQLPayload",
    "to_authenticated_user_graphql_payload",
    "to_authenticated_user_type",
]
