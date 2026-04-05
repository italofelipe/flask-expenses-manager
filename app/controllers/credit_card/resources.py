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
CREDIT_CARD_BRAND_VALUES = ("visa", "mastercard", "elo", "hipercard", "amex", "other")
INVALID_BRAND_MESSAGE = (
    "Field 'brand' must be one of: visa, mastercard, elo, hipercard, amex, other"
)
INVALID_DAY_MESSAGE = (
    "Fields 'closing_day' and 'due_day' must be integers between 1 and 28"
)


def _serialize_card(c: CreditCard) -> dict[str, Any]:
    return {
        "id": str(c.id),
        "name": c.name,
        "brand": c.brand,
        "limit_amount": float(c.limit_amount) if c.limit_amount is not None else None,
        "closing_day": c.closing_day,
        "due_day": c.due_day,
        "last_four_digits": c.last_four_digits,
    }


@credit_card_bp.route("", methods=["GET"])
@jwt_required()
def list_credit_cards() -> tuple[dict[str, Any], int]:
    """List all credit cards belonging to the authenticated user."""
    user_id = current_user_id()
    cards = CreditCard.query.filter_by(user_id=user_id).order_by(CreditCard.name).all()
    data = {
        "credit_cards": [_serialize_card(c) for c in cards],
        "total": len(cards),
    }
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Cartões listados com sucesso",
        data=data,
    )


def _validate_card_payload(
    payload: dict[str, Any],
) -> tuple[dict[str, Any], int] | None:
    """Validate brand, closing_day, due_day, last_four_digits.

    Returns an error tuple on invalid input, or None when all values are valid.
    """
    brand = payload.get("brand")
    if brand is not None and brand not in CREDIT_CARD_BRAND_VALUES:
        from app.controllers.response_contract import compat_error_tuple as _err

        return _err(
            legacy_payload={"error": INVALID_BRAND_MESSAGE},
            status_code=400,
            message=INVALID_BRAND_MESSAGE,
            error_code="INVALID_BRAND",
        )
    for day_field in ("closing_day", "due_day"):
        val = payload.get(day_field)
        if val is not None:
            try:
                v = int(val)
                if not (1 <= v <= 28):
                    raise ValueError
            except (ValueError, TypeError):
                from app.controllers.response_contract import compat_error_tuple as _err

                return _err(
                    legacy_payload={"error": INVALID_DAY_MESSAGE},
                    status_code=400,
                    message=INVALID_DAY_MESSAGE,
                    error_code="INVALID_DAY",
                )
    last_four = payload.get("last_four_digits")
    if last_four is not None and (
        not isinstance(last_four, str) or len(last_four) != 4
    ):
        from app.controllers.response_contract import compat_error_tuple as _err

        return _err(
            legacy_payload={
                "error": "Field 'last_four_digits' must be a 4-character string"
            },
            status_code=400,
            message="Field 'last_four_digits' must be a 4-character string",
            error_code="INVALID_LAST_FOUR_DIGITS",
        )
    return None


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

    validation_error = _validate_card_payload(payload)
    if validation_error is not None:
        return validation_error

    from decimal import Decimal

    limit_raw = payload.get("limit_amount")
    limit_amount = Decimal(str(limit_raw)) if limit_raw is not None else None

    closing_day_raw = payload.get("closing_day")
    closing_day = int(closing_day_raw) if closing_day_raw is not None else None

    due_day_raw = payload.get("due_day")
    due_day = int(due_day_raw) if due_day_raw is not None else None

    card = CreditCard(
        user_id=user_id,
        name=name,
        brand=payload.get("brand") or None,
        limit_amount=limit_amount,
        closing_day=closing_day,
        due_day=due_day,
        last_four_digits=payload.get("last_four_digits") or None,
    )
    db.session.add(card)
    db.session.commit()

    card_data = _serialize_card(card)
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

    validation_error = _validate_card_payload(payload)
    if validation_error is not None:
        return validation_error

    card.name = name
    if "brand" in payload:
        card.brand = payload.get("brand") or None
    if "limit_amount" in payload:
        from decimal import Decimal

        raw = payload["limit_amount"]
        card.limit_amount = Decimal(str(raw)) if raw is not None else None
    if "closing_day" in payload:
        raw_cd = payload["closing_day"]
        card.closing_day = int(raw_cd) if raw_cd is not None else None
    if "due_day" in payload:
        raw_dd = payload["due_day"]
        card.due_day = int(raw_dd) if raw_dd is not None else None
    if "last_four_digits" in payload:
        card.last_four_digits = payload.get("last_four_digits") or None
    db.session.commit()

    card_data = _serialize_card(card)
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
