from __future__ import annotations

from datetime import datetime
from typing import Any, cast
from uuid import UUID

from flask import Response
from sqlalchemy import extract
from sqlalchemy.orm.query import Query

from app.application.errors import PublicValidationError
from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.extensions.database import db
from app.models.transaction import Transaction
from app.models.user import User

from .contracts import compat_error


def _serialize_user_profile(user: User) -> dict[str, Any]:
    monthly_income = float(user.monthly_income) if user.monthly_income else None
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "gender": user.gender,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "monthly_income": monthly_income,
        "monthly_income_net": monthly_income,
        "net_worth": float(user.net_worth) if user.net_worth else None,
        "monthly_expenses": (
            float(user.monthly_expenses) if user.monthly_expenses else None
        ),
        "initial_investment": (
            float(user.initial_investment) if user.initial_investment else None
        ),
        "monthly_investment": (
            float(user.monthly_investment) if user.monthly_investment else None
        ),
        "investment_goal_date": (
            str(user.investment_goal_date) if user.investment_goal_date else None
        ),
        "state_uf": user.state_uf,
        "occupation": user.occupation,
        "investor_profile": user.investor_profile,
        "financial_objectives": user.financial_objectives,
    }


def assign_user_profile_fields(
    user: User, data: dict[str, Any]
) -> dict[str, str | bool]:
    date_fields = ["birth_date", "investment_goal_date"]
    for field in [
        "gender",
        "birth_date",
        "monthly_income",
        "net_worth",
        "monthly_expenses",
        "initial_investment",
        "monthly_investment",
        "investment_goal_date",
    ]:
        if field in data:
            value = data[field]
            if field in date_fields and isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return {
                        "error": True,
                        "message": (
                            f"Formato inválido para '{field}'. Use 'YYYY-MM-DD'."
                        ),
                    }
            setattr(user, field, value)
    return {"error": False}


def validate_user_token(user_id: UUID, jti: str) -> User | Response:
    user = cast(User | None, db.session.get(User, user_id))
    if not user or not hasattr(user, "current_jti") or user.current_jti != jti:
        return compat_error(
            legacy_payload={"message": "Token revogado ou usuário não encontrado"},
            status_code=401,
            message="Token revogado ou usuário não encontrado",
            error_code="UNAUTHORIZED",
        )
    return user


def filter_transactions(
    user_id: UUID, status: str | None, month: str | None
) -> Query[Any] | Response:
    query = cast(
        Query[Any], Transaction.query.filter_by(user_id=user_id, deleted=False)
    )

    if status:
        try:
            from app.models.transaction import TransactionStatus

            query = query.filter(
                Transaction.status == TransactionStatus(status.lower())
            )
        except ValueError:
            return compat_error(
                legacy_payload={"message": f"Status inválido: {status}"},
                status_code=400,
                message=f"Status inválido: {status}",
                error_code="VALIDATION_ERROR",
            )

    if month:
        try:
            year, month_num = map(int, month.split("-"))
            query = query.filter(
                extract("year", Transaction.due_date) == year,
                extract("month", Transaction.due_date) == month_num,
            )
        except ValueError:
            return compat_error(
                legacy_payload={
                    "message": "Parâmetro 'month' inválido. Use o formato YYYY-MM"
                },
                status_code=400,
                message="Parâmetro 'month' inválido. Use o formato YYYY-MM",
                error_code="VALIDATION_ERROR",
            )

    return query


def _parse_positive_int(
    raw_value: str | None,
    *,
    default: int,
    field_name: str,
    max_value: int,
) -> int:
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError:
        raise PublicValidationError(
            f"Parâmetro '{field_name}' inválido. Informe um inteiro positivo."
        )
    if parsed < 1 or parsed > max_value:
        raise PublicValidationError(
            f"Parâmetro '{field_name}' inválido. Use um valor entre 1 e {max_value}."
        )
    return parsed


def _validation_error_response(
    *,
    exc: Exception,
    legacy_key: str = "message",
    fallback_message: str,
) -> Response:
    mapped_error = map_validation_exception(exc, fallback_message=fallback_message)
    return compat_error(
        legacy_payload={legacy_key: mapped_error.message},
        status_code=mapped_error.status_code,
        message=mapped_error.message,
        error_code=mapped_error.code,
        details=mapped_error.details,
    )
