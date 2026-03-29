"""CreditCard controller resources — CRUD endpoints for user credit cards."""

from __future__ import annotations

# mypy: disable-error-code=untyped-decorator
from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.extensions.database import db
from app.models.credit_card import CreditCard
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import credit_card_bp

MISSING_NAME_MESSAGE = "Field 'name' is required"
NAME_TOO_LONG_MESSAGE = "Field 'name' must be at most 100 characters"
CREDIT_CARD_NOT_FOUND_MESSAGE = "Credit card not found"


@credit_card_bp.route("", methods=["GET"])
@jwt_required()
def list_credit_cards() -> tuple[dict[str, Any], int]:
    """List all credit cards belonging to the authenticated user."""
    user_id = current_user_id()
    cards = CreditCard.query.filter_by(user_id=user_id).order_by(CreditCard.name).all()
    data = {
        "credit_cards": [{"id": str(c.id), "name": c.name} for c in cards],
        "total": len(cards),
    }
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Cartões listados com sucesso",
        data=data,
    )


@credit_card_bp.route("", methods=["POST"])
@jwt_required()
def create_credit_card() -> tuple[dict[str, Any], int]:
    """Create a new credit card for the authenticated user."""
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

    card = CreditCard(user_id=user_id, name=name)
    db.session.add(card)
    db.session.commit()

    card_data = {"id": str(card.id), "name": card.name}
    return compat_success_tuple(
        legacy_payload={
            "message": "Cartão criado com sucesso",
            "credit_card": card_data,
        },
        status_code=201,
        message="Cartão criado com sucesso",
        data={"credit_card": card_data},
    )


@credit_card_bp.route("/<uuid:credit_card_id>", methods=["PUT"])
@jwt_required()
def update_credit_card(credit_card_id: UUID) -> tuple[dict[str, Any], int]:
    """Update an existing credit card belonging to the authenticated user."""
    user_id = current_user_id()
    card = CreditCard.query.filter_by(id=credit_card_id, user_id=user_id).first()
    if card is None:
        return compat_error_tuple(
            legacy_payload={"error": CREDIT_CARD_NOT_FOUND_MESSAGE},
            status_code=404,
            message=CREDIT_CARD_NOT_FOUND_MESSAGE,
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

    card.name = name
    db.session.commit()

    card_data = {"id": str(card.id), "name": card.name}
    return compat_success_tuple(
        legacy_payload={
            "message": "Cartão atualizado com sucesso",
            "credit_card": card_data,
        },
        status_code=200,
        message="Cartão atualizado com sucesso",
        data={"credit_card": card_data},
    )


@credit_card_bp.route("/<uuid:credit_card_id>", methods=["DELETE"])
@jwt_required()
def delete_credit_card(credit_card_id: UUID) -> tuple[dict[str, Any], int]:
    """Delete a credit card belonging to the authenticated user."""
    user_id = current_user_id()
    card = CreditCard.query.filter_by(id=credit_card_id, user_id=user_id).first()
    if card is None:
        return compat_error_tuple(
            legacy_payload={"error": CREDIT_CARD_NOT_FOUND_MESSAGE},
            status_code=404,
            message=CREDIT_CARD_NOT_FOUND_MESSAGE,
            error_code="NOT_FOUND",
        )

    db.session.delete(card)
    db.session.commit()

    return compat_success_tuple(
        legacy_payload={"message": "Cartão removido com sucesso"},
        status_code=200,
        message="Cartão removido com sucesso",
        data={},
    )
