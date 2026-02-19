from __future__ import annotations

from app.controllers.transaction.utils import serialize_transaction
from app.graphql.types import PaginationType, TransactionTypeObject
from app.models.transaction import Transaction


def paginate(*, total: int, page: int, per_page: int) -> PaginationType:
    pages = (total + per_page - 1) // per_page if total else 0
    return PaginationType(total=total, page=page, per_page=per_page, pages=pages)


def serialize_transaction_items(
    transactions: list[Transaction],
) -> list[TransactionTypeObject]:
    return [
        TransactionTypeObject(**serialize_transaction(item)) for item in transactions
    ]
