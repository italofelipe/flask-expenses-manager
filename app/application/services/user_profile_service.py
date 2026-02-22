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


def update_user_profile(user: User, data: dict[str, Any]) -> dict[str, str | None]:
    investor_profile = _normalize_investor_profile(data.get("investor_profile"))
    if "investor_profile" in data:
        if investor_profile is None:
            user.investor_profile = None
        elif investor_profile not in VALID_INVESTOR_PROFILES:
            return {
                "error": (
                    "Perfil do investidor inválido: " f"{data.get('investor_profile')}"
                )
            }
        else:
            user.investor_profile = investor_profile

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
