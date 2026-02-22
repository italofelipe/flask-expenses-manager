from __future__ import annotations

from datetime import date, datetime
from typing import Any, cast
from uuid import UUID

from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_FORBIDDEN,
    GRAPHQL_ERROR_CODE_NOT_FOUND,
    GRAPHQL_ERROR_CODE_VALIDATION,
    build_public_graphql_error,
)
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.user import User
from app.models.wallet import Wallet


def _to_float_or_none(value: Any) -> float | None:
    return float(value) if value is not None else None


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise build_public_graphql_error(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        ) from exc


def _parse_month(month: str) -> tuple[int, int]:
    try:
        year, month_number = map(int, month.split("-"))
    except ValueError as exc:
        raise build_public_graphql_error(
            "Formato de mês inválido. Use YYYY-MM.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        ) from exc
    if month_number < 1 or month_number > 12:
        raise build_public_graphql_error(
            "Formato de mês inválido. Use YYYY-MM.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        )
    return year, month_number


def _wallet_to_graphql_payload(wallet: Wallet) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(wallet.id),
        "name": wallet.name,
        "value": float(wallet.value) if wallet.value is not None else None,
        "estimated_value_on_create_date": (
            float(wallet.estimated_value_on_create_date)
            if wallet.estimated_value_on_create_date is not None
            else None
        ),
        "ticker": wallet.ticker,
        "quantity": wallet.quantity,
        "asset_class": wallet.asset_class or "custom",
        "annual_rate": (
            float(wallet.annual_rate) if wallet.annual_rate is not None else None
        ),
        "register_date": wallet.register_date.isoformat(),
        "target_withdraw_date": (
            wallet.target_withdraw_date.isoformat()
            if wallet.target_withdraw_date
            else None
        ),
        "should_be_on_wallet": wallet.should_be_on_wallet,
    }
    if payload["ticker"] is None:
        payload.pop("estimated_value_on_create_date", None)
        payload.pop("ticker", None)
        payload.pop("quantity", None)
    else:
        payload.pop("value", None)
    return payload


def _user_to_graphql_payload(user: User) -> dict[str, Any]:
    monthly_income = _to_float_or_none(user.monthly_income)
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "gender": user.gender,
        "birth_date": user.birth_date.isoformat() if user.birth_date else None,
        "monthly_income": monthly_income,
        "monthly_income_net": monthly_income,
        "net_worth": _to_float_or_none(user.net_worth),
        "monthly_expenses": _to_float_or_none(user.monthly_expenses),
        "initial_investment": _to_float_or_none(user.initial_investment),
        "monthly_investment": _to_float_or_none(user.monthly_investment),
        "investment_goal_date": (
            user.investment_goal_date.isoformat() if user.investment_goal_date else None
        ),
        "state_uf": user.state_uf,
        "occupation": user.occupation,
        "investor_profile": user.investor_profile,
        "financial_objectives": user.financial_objectives,
    }


def _user_basic_auth_payload(user: User) -> dict[str, str]:
    return {"id": str(user.id), "name": user.name, "email": user.email}


def _validate_pagination_values(
    page: int, per_page: int, *, max_per_page: int = 100
) -> None:
    if page < 1:
        raise build_public_graphql_error(
            "Parâmetro 'page' inválido. Informe um inteiro positivo.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        )
    if per_page < 1 or per_page > max_per_page:
        raise build_public_graphql_error(
            f"Parâmetro 'per_page' inválido. Use um valor entre 1 e {max_per_page}.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        )


def _apply_type_filter(query: Any, raw_type: str | None) -> Any:
    if not raw_type:
        return query
    try:
        return query.filter(Transaction.type == TransactionType(raw_type.lower()))
    except ValueError as exc:
        raise build_public_graphql_error(
            "Parâmetro 'type' inválido. Use 'income' ou 'expense'.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        ) from exc


def _apply_status_filter(query: Any, raw_status: str | None) -> Any:
    if not raw_status:
        return query
    try:
        return query.filter(Transaction.status == TransactionStatus(raw_status.lower()))
    except ValueError as exc:
        raise build_public_graphql_error(
            "Parâmetro 'status' inválido. "
            "Use paid, pending, cancelled, postponed ou overdue.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        ) from exc


def _apply_due_date_range_filter(
    query: Any,
    start_date: str | None,
    end_date: str | None,
) -> Any:
    parsed_start_date = _parse_optional_date(start_date, "start_date")
    parsed_end_date = _parse_optional_date(end_date, "end_date")
    if parsed_start_date and parsed_end_date and parsed_start_date > parsed_end_date:
        raise build_public_graphql_error(
            "Parâmetro 'start_date' não pode ser maior que 'end_date'.",
            code=GRAPHQL_ERROR_CODE_VALIDATION,
        )
    if parsed_start_date:
        query = query.filter(Transaction.due_date >= parsed_start_date)
    if parsed_end_date:
        query = query.filter(Transaction.due_date <= parsed_end_date)
    return query


def _get_owned_wallet_or_error(
    investment_id: UUID,
    user_id: UUID,
    *,
    forbidden_message: str,
) -> Wallet:
    investment = cast(Wallet | None, Wallet.query.filter_by(id=investment_id).first())
    if not investment:
        raise build_public_graphql_error(
            "Investimento não encontrado",
            code=GRAPHQL_ERROR_CODE_NOT_FOUND,
        )
    if str(investment.user_id) != str(user_id):
        raise build_public_graphql_error(
            forbidden_message,
            code=GRAPHQL_ERROR_CODE_FORBIDDEN,
        )
    return investment


def _assert_owned_investment_access(investment_id: UUID, user_id: UUID) -> None:
    _get_owned_wallet_or_error(
        investment_id,
        user_id,
        forbidden_message="Você não tem permissão para acessar este investimento.",
    )
