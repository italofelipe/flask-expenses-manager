"""Generic CSV ingestion service for fiscal/receivable data.

Supports flexible Brazilian CSV formats with configurable column mappings.
"""

from __future__ import annotations

import csv
import io
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any

from app.extensions.database import db
from app.models.fiscal import (
    FiscalDocument,
    FiscalDocumentType,
    FiscalImport,
    FiscalImportStatus,
    ReceivableEntry,
    ReconciliationStatus,
)

_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
]

_AMOUNT_TRANSLATION = str.maketrans({"R": "", "$": "", " ": "", "\xa0": ""})


@dataclass
class ParsedRow:
    description: str
    amount: Decimal
    date: date
    category: str | None = None
    external_id: str | None = None


@dataclass
class ParseResult:
    rows: list[ParsedRow] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)


def _parse_amount(raw: str) -> Decimal:
    """Parse Brazilian or international amount strings to Decimal."""
    value = raw.strip().translate(_AMOUNT_TRANSLATION)
    # Handle "1.234,56" (Brazilian) → "1234.56"
    if "," in value and "." in value:
        if value.index(",") > value.index("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        value = value.replace(",", ".")
    try:
        return Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Cannot parse amount: {raw!r}") from exc


def _parse_date(raw: str) -> date:
    """Parse date strings in common Brazilian and ISO formats."""
    from datetime import datetime

    raw = raw.strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Cannot parse date: {raw!r}")


def parse_csv_generic(content: str, column_map: dict[str, str]) -> ParseResult:
    """Parse a CSV string using a flexible column mapping.

    Args:
        content: Raw CSV text content.
        column_map: Maps CSV header names to ParsedRow field names.
            Required mappings: ``description``, ``amount``, ``date``.
            Optional mappings: ``category``, ``external_id``.

    Returns:
        ParseResult with successfully parsed rows and any per-row errors.
    """
    result = ParseResult()
    reader = csv.DictReader(io.StringIO(content))

    reverse_map = {v: k for k, v in column_map.items()}

    def _get(row: dict[str, str], target_field: str) -> str | None:
        csv_col = reverse_map.get(target_field)
        if csv_col is None:
            return None
        return row.get(csv_col, "").strip() or None

    for line_number, row in enumerate(reader, start=2):
        try:
            description_raw = _get(row, "description")
            amount_raw = _get(row, "amount")
            date_raw = _get(row, "date")

            if not description_raw:
                raise ValueError("Missing required field: description")
            if not amount_raw:
                raise ValueError("Missing required field: amount")
            if not date_raw:
                raise ValueError("Missing required field: date")

            parsed = ParsedRow(
                description=description_raw,
                amount=_parse_amount(amount_raw),
                date=_parse_date(date_raw),
                category=_get(row, "category"),
                external_id=_get(row, "external_id"),
            )
            result.rows.append(parsed)
        except (ValueError, KeyError) as exc:
            result.errors.append(
                {"line": line_number, "error": str(exc), "raw": dict(row)}
            )

    return result


def ingest_as_receivables(
    user_id: str,
    rows: list[ParsedRow],
    import_id: str | None = None,
) -> list[FiscalDocument]:
    """Persist ParsedRows as FiscalDocument + ReceivableEntry records.

    Deduplicates by (user_id, external_id). Rows without external_id get a
    generated UUID as external_id to avoid unique-constraint collisions.

    Returns the list of created FiscalDocument records.
    """
    # Normalise to uuid.UUID so SQLite (used in tests) does not reject plain strings.
    user_uuid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
    import_uuid: uuid.UUID | None = None
    if import_id is not None:
        import_uuid = uuid.UUID(import_id) if isinstance(import_id, str) else import_id

    created: list[FiscalDocument] = []

    for row in rows:
        ext_id = row.external_id or str(uuid.uuid4())

        existing = FiscalDocument.query.filter_by(
            user_id=user_uuid, external_id=ext_id
        ).first()
        if existing is not None:
            continue

        doc = FiscalDocument(
            user_id=user_uuid,
            import_id=import_uuid,
            external_id=ext_id,
            type=FiscalDocumentType.SERVICE_INVOICE,
            issued_at=row.date,
            counterparty=row.description,
            gross_amount=row.amount,
            description=row.category,
        )
        db.session.add(doc)
        db.session.flush()

        entry = ReceivableEntry(
            fiscal_document_id=doc.id,
            user_id=user_uuid,
            expected_net_amount=row.amount,
            reconciliation_status=ReconciliationStatus.PENDING,
        )
        db.session.add(entry)
        created.append(doc)

    db.session.commit()
    return created


def create_import_batch(user_id: str, filename: str | None = None) -> FiscalImport:
    """Create a FiscalImport batch record in PROCESSING state."""
    batch = FiscalImport(
        user_id=uuid.UUID(user_id) if isinstance(user_id, str) else user_id,
        status=FiscalImportStatus.PROCESSING,
        filename=filename,
    )
    db.session.add(batch)
    db.session.commit()
    return batch


def finalize_import_batch(
    batch: FiscalImport,
    total_rows: int,
    valid_rows: int,
    error_rows: int,
    confirmed: bool = False,
) -> FiscalImport:
    """Update batch statistics and mark as PREVIEW_READY or CONFIRMED."""
    from app.utils.datetime_utils import utc_now_naive

    batch.total_rows = total_rows
    batch.valid_rows = valid_rows
    batch.error_rows = error_rows
    if confirmed:
        batch.status = FiscalImportStatus.CONFIRMED
        batch.confirmed_at = utc_now_naive()
    else:
        batch.status = FiscalImportStatus.PREVIEW_READY
    db.session.commit()
    return batch
