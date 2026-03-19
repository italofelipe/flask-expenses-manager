"""Fiscal documents service — CRUD operations for FiscalDocument."""

from __future__ import annotations

import uuid as _uuid
from datetime import date
from decimal import Decimal
from typing import Any, cast

from app.extensions.database import db
from app.models.fiscal import FiscalDocument, FiscalDocumentType


def _to_uuid(value: str | _uuid.UUID) -> _uuid.UUID:
    """Coerce a str or uuid.UUID to uuid.UUID (needed for SQLite in tests)."""
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


class FiscalDocumentNotFoundError(Exception):
    """Raised when a FiscalDocument is not found for the given user."""


def create_fiscal_document(
    user_id: str,
    doc_type: str,
    amount: Decimal,
    issued_at: date,
    counterpart_name: str | None = None,
    external_id: str | None = None,
    raw_data: dict[str, Any] | None = None,
) -> FiscalDocument:
    """Create a new FiscalDocument record.

    Args:
        user_id: UUID string of the owning user.
        doc_type: One of FiscalDocumentType enum values (e.g. "service_invoice").
        amount: Gross amount.
        issued_at: Issue date.
        counterpart_name: Name of counterparty (client / supplier).
        external_id: External reference ID; generated if not provided.
        raw_data: Optional arbitrary JSON data (stored in ``description`` field).

    Returns:
        Persisted FiscalDocument instance.
    """
    import json

    try:
        doc_type_enum = FiscalDocumentType(doc_type)
    except ValueError as exc:
        valid = [e.value for e in FiscalDocumentType]
        raise ValueError(
            f"Invalid doc_type {doc_type!r}. Valid values: {valid}"
        ) from exc

    ext_id = external_id or str(_uuid.uuid4())
    description: str | None = None
    if raw_data is not None:
        description = json.dumps(raw_data, ensure_ascii=False)

    doc = FiscalDocument(
        user_id=_to_uuid(user_id),
        external_id=ext_id,
        type=doc_type_enum,
        issued_at=issued_at,
        counterparty=counterpart_name or "",
        gross_amount=amount,
        description=description,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


def list_fiscal_documents(
    user_id: str,
    doc_type: str | None = None,
) -> list[FiscalDocument]:
    """List FiscalDocument records for a user.

    Args:
        user_id: Filter by user.
        doc_type: Optional FiscalDocumentType value to filter by.
    """
    query = FiscalDocument.query.filter_by(user_id=_to_uuid(user_id))
    if doc_type is not None:
        try:
            doc_type_enum = FiscalDocumentType(doc_type)
            query = query.filter_by(type=doc_type_enum)
        except ValueError:
            return []
    return cast(
        list[FiscalDocument], query.order_by(FiscalDocument.issued_at.desc()).all()
    )


def get_fiscal_document(doc_id: str, user_id: str) -> FiscalDocument:
    """Retrieve a single FiscalDocument by id, scoped to user.

    Raises:
        FiscalDocumentNotFoundError: if not found or belongs to another user.
    """
    doc = FiscalDocument.query.filter_by(
        id=_to_uuid(doc_id), user_id=_to_uuid(user_id)
    ).first()
    if doc is None:
        raise FiscalDocumentNotFoundError(f"FiscalDocument {doc_id} not found")
    return cast(FiscalDocument, doc)
