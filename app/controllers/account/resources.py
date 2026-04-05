"""Account controller resources — CRUD endpoints for user accounts."""

from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.extensions.database import db
from app.models.account import Account
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import account_bp

MISSING_NAME_MESSAGE = "Field 'name' is required"
NAME_TOO_LONG_MESSAGE = "Field 'name' must be at most 100 characters"
ACCOUNT_NOT_FOUND_MESSAGE = "Account not found"
ACCOUNT_TYPE_VALUES = ("checking", "savings", "investment", "wallet", "other")
INVALID_ACCOUNT_TYPE_MESSAGE = (
    "Field 'account_type' must be one of: checking, savings, investment, wallet, other"
)


def _serialize_account(a: Account) -> dict[str, Any]:
    return {
        "id": str(a.id),
        "name": a.name,
        "account_type": a.account_type or "checking",
        "institution": a.institution,
        "initial_balance": float(a.initial_balance)
        if a.initial_balance is not None
        else 0.0,
    }


@account_bp.route("", methods=["GET"])
@jwt_required()
def list_accounts() -> tuple[dict[str, Any], int]:
    """List all accounts belonging to the authenticated user."""
    user_id = current_user_id()
    accounts = Account.query.filter_by(user_id=user_id).order_by(Account.name).all()
    data = {
        "accounts": [_serialize_account(a) for a in accounts],
        "total": len(accounts),
    }
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Contas listadas com sucesso",
        data=data,
    )


@account_bp.route("", methods=["POST"])
@jwt_required()
def create_account() -> tuple[dict[str, Any], int]:
    """Create a new account for the authenticated user."""
    user_id = current_user_id()
    payload = request.get_json(silent=True) or {}

    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": MISSING_NAME_MESSAGE},
            status_code=400,
            message=MISSING_NAME_MESSAGE,
            error_code="MISSING_NAME",
        )
    if len(name) > 100:
        return compat_error_tuple(
            legacy_payload={"error": NAME_TOO_LONG_MESSAGE},
            status_code=400,
            message=NAME_TOO_LONG_MESSAGE,
            error_code="NAME_TOO_LONG",
        )

    account_type = payload.get("account_type", "checking") or "checking"
    if account_type not in ACCOUNT_TYPE_VALUES:
        return compat_error_tuple(
            legacy_payload={"error": INVALID_ACCOUNT_TYPE_MESSAGE},
            status_code=400,
            message=INVALID_ACCOUNT_TYPE_MESSAGE,
            error_code="INVALID_ACCOUNT_TYPE",
        )

    institution = payload.get("institution") or None
    try:
        from decimal import Decimal

        initial_balance = Decimal(str(payload.get("initial_balance", 0) or 0))
    except Exception:
        initial_balance = Decimal("0")

    account = Account(
        user_id=user_id,
        name=name,
        account_type=account_type,
        institution=institution,
        initial_balance=initial_balance,
    )
    db.session.add(account)
    db.session.commit()

    account_data = _serialize_account(account)
    return compat_success_tuple(
        legacy_payload={"message": "Conta criada com sucesso", "account": account_data},
        status_code=201,
        message="Conta criada com sucesso",
        data={"account": account_data},
    )


@account_bp.route("/<uuid:account_id>", methods=["PUT"])
@jwt_required()
def update_account(account_id: UUID) -> tuple[dict[str, Any], int]:
    """Update an existing account belonging to the authenticated user."""
    user_id = current_user_id()
    account = Account.query.filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        return compat_error_tuple(
            legacy_payload={"error": ACCOUNT_NOT_FOUND_MESSAGE},
            status_code=404,
            message=ACCOUNT_NOT_FOUND_MESSAGE,
            error_code="NOT_FOUND",
        )

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": MISSING_NAME_MESSAGE},
            status_code=400,
            message=MISSING_NAME_MESSAGE,
            error_code="MISSING_NAME",
        )
    if len(name) > 100:
        return compat_error_tuple(
            legacy_payload={"error": NAME_TOO_LONG_MESSAGE},
            status_code=400,
            message=NAME_TOO_LONG_MESSAGE,
            error_code="NAME_TOO_LONG",
        )

    account_type = payload.get("account_type", account.account_type) or "checking"
    if account_type not in ACCOUNT_TYPE_VALUES:
        return compat_error_tuple(
            legacy_payload={"error": INVALID_ACCOUNT_TYPE_MESSAGE},
            status_code=400,
            message=INVALID_ACCOUNT_TYPE_MESSAGE,
            error_code="INVALID_ACCOUNT_TYPE",
        )

    account.name = name
    account.account_type = account_type
    if "institution" in payload:
        account.institution = payload.get("institution") or None
    if "initial_balance" in payload:
        try:
            from decimal import Decimal

            account.initial_balance = Decimal(str(payload["initial_balance"] or 0))
        except Exception:
            pass
    db.session.commit()

    account_data = _serialize_account(account)
    return compat_success_tuple(
        legacy_payload={
            "message": "Conta atualizada com sucesso",
            "account": account_data,
        },
        status_code=200,
        message="Conta atualizada com sucesso",
        data={"account": account_data},
    )


@account_bp.route("/<uuid:account_id>", methods=["DELETE"])
@jwt_required()
def delete_account(account_id: UUID) -> tuple[dict[str, Any], int]:
    """Delete an account belonging to the authenticated user."""
    user_id = current_user_id()
    account = Account.query.filter_by(id=account_id, user_id=user_id).first()
    if account is None:
        return compat_error_tuple(
            legacy_payload={"error": ACCOUNT_NOT_FOUND_MESSAGE},
            status_code=404,
            message=ACCOUNT_NOT_FOUND_MESSAGE,
            error_code="NOT_FOUND",
        )

    db.session.delete(account)
    db.session.commit()

    return compat_success_tuple(
        legacy_payload={"message": "Conta removida com sucesso"},
        status_code=200,
        message="Conta removida com sucesso",
        data={},
    )
