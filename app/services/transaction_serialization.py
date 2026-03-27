from __future__ import annotations

from typing import TypedDict

from app.models.transaction import Transaction


class TransactionPayload(TypedDict):
    id: str
    title: str
    amount: str
    type: str
    due_date: str
    start_date: str | None
    end_date: str | None
    description: str | None
    observation: str | None
    is_recurring: bool
    is_installment: bool
    installment_count: int | None
    tag_id: str | None
    account_id: str | None
    credit_card_id: str | None
    status: str
    currency: str
    source: str
    external_id: str | None
    bank_name: str | None
    created_at: str | None
    updated_at: str | None


def serialize_transaction_payload(transaction: Transaction) -> TransactionPayload:
    return {
        "id": str(transaction.id),
        "title": transaction.title,
        "amount": str(transaction.amount),
        "type": transaction.type.value,
        "due_date": transaction.due_date.isoformat(),
        "start_date": (
            transaction.start_date.isoformat() if transaction.start_date else None
        ),
        "end_date": transaction.end_date.isoformat() if transaction.end_date else None,
        "description": transaction.description,
        "observation": transaction.observation,
        "is_recurring": transaction.is_recurring,
        "is_installment": transaction.is_installment,
        "installment_count": transaction.installment_count,
        "tag_id": str(transaction.tag_id) if transaction.tag_id else None,
        "account_id": str(transaction.account_id) if transaction.account_id else None,
        "credit_card_id": (
            str(transaction.credit_card_id) if transaction.credit_card_id else None
        ),
        "status": transaction.status.value,
        "currency": transaction.currency,
        "source": transaction.source or "manual",
        "external_id": transaction.external_id,
        "bank_name": transaction.bank_name,
        "created_at": (
            transaction.created_at.isoformat() if transaction.created_at else None
        ),
        "updated_at": (
            transaction.updated_at.isoformat() if transaction.updated_at else None
        ),
    }


__all__ = ["TransactionPayload", "serialize_transaction_payload"]
