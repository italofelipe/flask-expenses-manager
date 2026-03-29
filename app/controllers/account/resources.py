"""Account controller resources — CRUD endpoints for user accounts."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.extensions.database import db
from app.models.account import Account
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import account_bp


@account_bp.route("", methods=["GET"])
@jwt_required()
def list_accounts() -> tuple[dict[str, Any], int]:
    """List all accounts belonging to the authenticated user."""
    user_id = current_user_id()
    accounts = Account.query.filter_by(user_id=user_id).order_by(Account.name).all()
    data = {
        "accounts": [{"id": str(a.id), "name": a.name} for a in accounts],
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
            legacy_payload={"error": "Field 'name' is required"},
            status_code=400,
            message="Field 'name' is required",
            error_code="MISSING_NAME",
        )
    if len(name) > 100:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' must be at most 100 characters"},
            status_code=400,
            message="Field 'name' must be at most 100 characters",
            error_code="NAME_TOO_LONG",
        )

    account = Account(user_id=user_id, name=name)
    db.session.add(account)
    db.session.commit()

    account_data = {"id": str(account.id), "name": account.name}
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
            legacy_payload={"error": "Account not found"},
            status_code=404,
            message="Account not found",
            error_code="NOT_FOUND",
        )

    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' is required"},
            status_code=400,
            message="Field 'name' is required",
            error_code="MISSING_NAME",
        )
    if len(name) > 100:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'name' must be at most 100 characters"},
            status_code=400,
            message="Field 'name' must be at most 100 characters",
            error_code="NAME_TOO_LONG",
        )

    account.name = name
    db.session.commit()

    account_data = {"id": str(account.id), "name": account.name}
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
            legacy_payload={"error": "Account not found"},
            status_code=404,
            message="Account not found",
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
