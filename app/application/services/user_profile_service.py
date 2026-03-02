from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models.user import User

INVESTOR_PROFILE_CHOICES = ("conservador", "explorador", "entusiasta")
VALID_INVESTOR_PROFILES = set(INVESTOR_PROFILE_CHOICES)

_DATE_FIELDS = {"birth_date", "investment_goal_date"}
_PROFILE_MUTABLE_FIELDS = (
    "gender",
    "birth_date",
    "monthly_income",
    "monthly_income_net",
    "net_worth",
    "monthly_expenses",
    "initial_investment",
    "monthly_investment",
    "investment_goal_date",
    "state_uf",
    "occupation",
    "financial_objectives",
    # B11: investor profile suggestion fields (persisted from quiz results)
    "profile_quiz_score",
    "taxonomy_version",
)


def _parse_date(field_name: str, value: Any) -> tuple[Any, str | None]:
    if value is None or not isinstance(value, str):
        return value, None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date(), None
    except ValueError:
        return None, f"Formato inválido para '{field_name}'. Use 'YYYY-MM-DD'."


def _normalize_investor_profile(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    return normalized


def _apply_declared_investor_profile(user: User, data: dict[str, Any]) -> str | None:
    """Apply investor_profile (declared). Returns an error string or None."""
    if "investor_profile" not in data:
        return None
    normalized = _normalize_investor_profile(data["investor_profile"])
    if normalized is None:
        user.investor_profile = None
        return None
    if normalized not in VALID_INVESTOR_PROFILES:
        return f"Perfil do investidor inválido: {data['investor_profile']}"
    user.investor_profile = normalized
    return None


def _apply_suggested_investor_profile(user: User, data: dict[str, Any]) -> None:
    """Apply investor_profile_suggested (B11 — quiz-derived, any lowercase string)."""
    if "investor_profile_suggested" in data:
        user.investor_profile_suggested = _normalize_investor_profile(
            data["investor_profile_suggested"]
        )


def update_user_profile(user: User, data: dict[str, Any]) -> dict[str, str | None]:
    error = _apply_declared_investor_profile(user, data)
    if error:
        return {"error": error}

    _apply_suggested_investor_profile(user, data)

    for field in _PROFILE_MUTABLE_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if field in _DATE_FIELDS:
            parsed_value, error = _parse_date(field, value)
            if error:
                return {"error": error}
            value = parsed_value
        if field == "state_uf" and isinstance(value, str):
            value = value.upper()
        if field == "monthly_income_net":
            user.monthly_income_net = value
            continue
        setattr(user, field, value)

    return {"error": None}
