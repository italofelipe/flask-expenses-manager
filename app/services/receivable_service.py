"""Receivable entries service — CRUD and revenue summary.

IMPORTANT: ``expected_net_amount`` on ReceivableEntry is **advisory-only** and
must NEVER be presented as an official fiscal calculation without the disclaimer:
  "Este valor é estimativo e não substitui cálculo fiscal por profissional habilitado"
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from app.extensions.database import db
from app.models.fiscal import (
    FiscalDocument,
    FiscalDocumentType,
    ReceivableEntry,
    ReconciliationStatus,
)
from app.utils.datetime_utils import utc_now_naive


def _to_uuid(value: str | _uuid.UUID) -> _uuid.UUID:
    """Coerce a str or uuid.UUID to uuid.UUID (needed for SQLite in tests)."""
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


class ReceivableNotFoundError(Exception):
    """Raised when a ReceivableEntry is not found for the given user."""


class ReceivableAlreadySettledError(Exception):
    """Raised when attempting to modify an already-settled receivable."""


def create_receivable(
    user_id: str,
    description: str,
    amount: Decimal,
    expected_date: date,
    category: str | None = None,
) -> tuple[FiscalDocument, ReceivableEntry]:
    """Create a manual FiscalDocument + ReceivableEntry pair.

    Returns:
        Tuple of (FiscalDocument, ReceivableEntry).
    """
    user_uuid = _to_uuid(user_id)

    doc = FiscalDocument(
        user_id=user_uuid,
        external_id=str(_uuid.uuid4()),
        type=FiscalDocumentType.SERVICE_INVOICE,
        issued_at=expected_date,
        counterparty=description,
        gross_amount=amount,
        description=category,
    )
    db.session.add(doc)
    db.session.flush()

    entry = ReceivableEntry(
        fiscal_document_id=doc.id,
        user_id=user_uuid,
        expected_net_amount=amount,
        reconciliation_status=ReconciliationStatus.PENDING,
    )
    db.session.add(entry)
    db.session.commit()
    return doc, entry


def mark_received(
    entry_id: str,
    user_id: str,
    received_date: date,
    received_amount: Decimal | None = None,
) -> ReceivableEntry:
    """Mark a ReceivableEntry as RECONCILED (received).

    Args:
        entry_id: UUID of the ReceivableEntry.
        user_id: Must match entry's user_id.
        received_date: Date the payment was received.
        received_amount: Actual amount received; defaults to expected_net_amount.

    Raises:
        ReceivableNotFoundError: entry not found or belongs to another user.
        ReceivableAlreadySettledError: entry already reconciled.
    """
    entry = ReceivableEntry.query.filter_by(
        id=_to_uuid(entry_id), user_id=_to_uuid(user_id)
    ).first()
    if entry is None:
        raise ReceivableNotFoundError(f"ReceivableEntry {entry_id} not found")
    if entry.reconciliation_status == ReconciliationStatus.RECONCILED:
        raise ReceivableAlreadySettledError(
            f"ReceivableEntry {entry_id} is already reconciled"
        )

    actual = (
        received_amount if received_amount is not None else entry.expected_net_amount
    )
    entry.received_amount = actual
    entry.received_at = utc_now_naive()
    entry.reconciliation_status = ReconciliationStatus.RECONCILED
    if entry.expected_net_amount is not None and actual is not None:
        outstanding = entry.expected_net_amount - actual
        entry.outstanding_amount = outstanding
    else:
        entry.outstanding_amount = Decimal("0")
    db.session.commit()
    return cast(ReceivableEntry, entry)


def cancel_receivable(entry_id: str, user_id: str) -> ReceivableEntry:
    """Mark a ReceivableEntry as PARTIAL (cancelled/written-off).

    Raises:
        ReceivableNotFoundError: entry not found or belongs to another user.
        ReceivableAlreadySettledError: entry already reconciled.
    """
    entry = ReceivableEntry.query.filter_by(
        id=_to_uuid(entry_id), user_id=_to_uuid(user_id)
    ).first()
    if entry is None:
        raise ReceivableNotFoundError(f"ReceivableEntry {entry_id} not found")
    if entry.reconciliation_status == ReconciliationStatus.RECONCILED:
        raise ReceivableAlreadySettledError(
            f"Cannot cancel an already-reconciled entry {entry_id}"
        )

    entry.reconciliation_status = ReconciliationStatus.PARTIAL
    db.session.commit()
    return cast(ReceivableEntry, entry)


def list_receivables(
    user_id: str,
    status: str | None = None,
) -> list[ReceivableEntry]:
    """List ReceivableEntry records for a user.

    Args:
        user_id: Filter by user.
        status: Optional filter: "pending" | "received" | "cancelled".
            Maps to ReconciliationStatus values.
    """
    query = ReceivableEntry.query.filter_by(user_id=_to_uuid(user_id))

    _status_map = {
        "pending": ReconciliationStatus.PENDING,
        "received": ReconciliationStatus.RECONCILED,
        "cancelled": ReconciliationStatus.PARTIAL,
    }
    if status is not None:
        mapped = _status_map.get(status)
        if mapped is not None:
            query = query.filter_by(reconciliation_status=mapped)

    return cast(
        list[ReceivableEntry], query.order_by(ReceivableEntry.created_at.desc()).all()
    )


def get_revenue_summary(user_id: str) -> dict[str, Any]:
    """Return aggregated revenue totals for a user.

    Returns:
        Dict with keys:
        - ``expected_total``: sum of expected_net_amount across all entries
        - ``received_total``: sum of received_amount for RECONCILED entries
        - ``pending_total``: sum of expected_net_amount for PENDING entries
        - ``disclaimer``: mandatory advisory text

    IMPORTANT: These values are advisory only.
    """

    all_entries = ReceivableEntry.query.filter_by(user_id=_to_uuid(user_id)).all()

    expected_total = sum((e.expected_net_amount or Decimal("0")) for e in all_entries)
    received_total = sum(
        (e.received_amount or Decimal("0"))
        for e in all_entries
        if e.reconciliation_status == ReconciliationStatus.RECONCILED
    )
    pending_total = sum(
        (e.expected_net_amount or Decimal("0"))
        for e in all_entries
        if e.reconciliation_status == ReconciliationStatus.PENDING
    )

    return {
        "expected_total": str(expected_total),
        "received_total": str(received_total),
        "pending_total": str(pending_total),
        "disclaimer": (
            "Este valor é estimativo e não substitui cálculo fiscal "
            "por profissional habilitado"
        ),
    }
