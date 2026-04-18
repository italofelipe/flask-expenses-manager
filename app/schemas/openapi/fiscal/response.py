"""Serialisation helpers for the fiscal domain."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.services.csv_ingestion_service import ParsedRow


def serialize_row(row: ParsedRow) -> dict[str, Any]:
    return {
        "description": row.description,
        "amount": str(row.amount),
        "date": row.date.isoformat(),
        "category": row.category,
        "external_id": row.external_id,
    }


def serialize_entry(entry: Any) -> dict[str, Any]:
    return {
        "id": str(entry.id),
        "fiscal_document_id": str(entry.fiscal_document_id),
        "expected_net_amount": (
            str(entry.expected_net_amount)
            if entry.expected_net_amount is not None
            else None
        ),
        "received_amount": (
            str(entry.received_amount) if entry.received_amount is not None else None
        ),
        "outstanding_amount": (
            str(entry.outstanding_amount)
            if entry.outstanding_amount is not None
            else None
        ),
        "reconciliation_status": entry.reconciliation_status.value,
        "received_at": entry.received_at.isoformat() if entry.received_at else None,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "disclaimer": (
            "Este valor é estimativo e não substitui cálculo fiscal "
            "por profissional habilitado"
        ),
    }


def serialize_document(doc: Any) -> dict[str, Any]:
    return {
        "id": str(doc.id),
        "external_id": doc.external_id,
        "type": doc.type.value,
        "status": doc.status.value,
        "issued_at": doc.issued_at.isoformat() if doc.issued_at else None,
        "counterparty": doc.counterparty,
        "gross_amount": str(doc.gross_amount),
        "currency": doc.currency,
        "description": doc.description,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }
