from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.account import Account
from app.models.credit_card import CreditCard
from app.models.tag import Tag


class TransactionReferenceAuthorizationError(Exception):
    pass


def enforce_transaction_reference_ownership(
    *,
    user_id: UUID,
    tag_id: UUID | None,
    account_id: UUID | None,
    credit_card_id: UUID | None,
) -> None:
    checks: tuple[tuple[str, UUID | None, Any], ...] = (
        ("tag_id", tag_id, Tag),
        ("account_id", account_id, Account),
        ("credit_card_id", credit_card_id, CreditCard),
    )
    for field_name, resource_id, model in checks:
        if resource_id is None:
            continue
        owned = (
            model.query.filter_by(id=resource_id, user_id=user_id).first() is not None
        )
        if owned:
            continue
        raise TransactionReferenceAuthorizationError(
            f"Referência inválida para '{field_name}'."
        )
