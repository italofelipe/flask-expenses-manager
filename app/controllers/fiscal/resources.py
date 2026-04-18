"""Fiscal controller resources — CSV ingestion, receivables, fiscal documents."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.schemas.openapi.fiscal.response import (
    serialize_document as _serialise_document,
)
from app.schemas.openapi.fiscal.response import (
    serialize_entry as _serialise_entry,
)
from app.schemas.openapi.fiscal.response import (
    serialize_row as _serialise_row,
)
from app.services.csv_ingestion_service import (
    ParseResult,
    create_import_batch,
    finalize_import_batch,
    ingest_as_receivables,
    parse_csv_generic,
)
from app.services.fiscal_service import (
    create_fiscal_document,
    list_fiscal_documents,
)
from app.services.receivable_service import (
    ReceivableAlreadySettledError,
    ReceivableNotFoundError,
    cancel_receivable,
    create_receivable,
    get_revenue_summary,
    list_receivables,
    mark_received,
)
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .blueprint import fiscal_bp


def _parse_date_param(value: str) -> date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {value!r}. Use YYYY-MM-DD.")


# ---------------------------------------------------------------------------
# CSV endpoints
# ---------------------------------------------------------------------------


@fiscal_bp.route("/csv/upload", methods=["POST"])
@jwt_required()
def csv_upload() -> tuple[dict[str, Any], int]:
    """Upload CSV and return a preview of parsed rows (nothing is persisted)."""
    current_user_id()  # Validates that the caller is authenticated
    payload = request.get_json(silent=True) or {}

    content = payload.get("content", "")
    column_map = payload.get("column_map", {})

    if not content:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'content' is required"},
            status_code=400,
            message="Field 'content' is required",
            error_code="MISSING_CONTENT",
        )

    if not column_map:
        column_map = {
            "description": "description",
            "amount": "amount",
            "date": "date",
            "category": "category",
            "external_id": "external_id",
        }

    result: ParseResult = parse_csv_generic(content, column_map)
    preview = [_serialise_row(r) for r in result.rows]

    data = {
        "preview": preview,
        "total_rows": len(result.rows) + len(result.errors),
        "valid_rows": len(result.rows),
        "error_rows": len(result.errors),
        "errors": result.errors,
    }
    return compat_success_tuple(
        legacy_payload={"message": "Preview gerado com sucesso", **data},
        status_code=200,
        message="Preview gerado com sucesso",
        data=data,
    )


@fiscal_bp.route("/csv/confirm", methods=["POST"])
@jwt_required()
def csv_confirm() -> tuple[dict[str, Any], int]:
    """Confirm a previously previewed CSV import and persist ReceivableEntry records."""
    user_id = str(current_user_id())
    payload = request.get_json(silent=True) or {}

    content = payload.get("content", "")
    column_map = payload.get("column_map", {})
    filename = payload.get("filename")

    if not content:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'content' is required"},
            status_code=400,
            message="Field 'content' is required",
            error_code="MISSING_CONTENT",
        )

    if not column_map:
        column_map = {
            "description": "description",
            "amount": "amount",
            "date": "date",
            "category": "category",
            "external_id": "external_id",
        }

    batch = create_import_batch(user_id, filename=filename)
    result: ParseResult = parse_csv_generic(content, column_map)
    created_docs = ingest_as_receivables(user_id, result.rows, import_id=str(batch.id))
    finalize_import_batch(
        batch,
        total_rows=len(result.rows) + len(result.errors),
        valid_rows=len(result.rows),
        error_rows=len(result.errors),
        confirmed=True,
    )

    data = {
        "import_id": str(batch.id),
        "imported_count": len(created_docs),
        "skipped_duplicates": len(result.rows) - len(created_docs),
        "error_rows": len(result.errors),
        "errors": result.errors,
    }
    return compat_success_tuple(
        legacy_payload={"message": "Importação confirmada com sucesso", **data},
        status_code=201,
        message="Importação confirmada com sucesso",
        data=data,
    )


# ---------------------------------------------------------------------------
# Receivable endpoints
# ---------------------------------------------------------------------------


@fiscal_bp.route("/receivables", methods=["GET"])
@jwt_required()
def get_receivables() -> tuple[dict[str, Any], int]:
    """List receivable entries for the current user."""
    user_id = str(current_user_id())
    status = request.args.get("status")
    entries = list_receivables(user_id, status=status)
    serialised = [_serialise_entry(e) for e in entries]
    data = {"receivables": serialised, "count": len(serialised)}
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Recebíveis listados com sucesso",
        data=data,
    )


@fiscal_bp.route("/receivables", methods=["POST"])
@jwt_required()
def create_receivable_entry() -> tuple[dict[str, Any], int]:
    """Create a manual receivable entry."""
    user_id = str(current_user_id())
    payload = request.get_json(silent=True) or {}

    required = ("description", "amount", "expected_date")
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return compat_error_tuple(
            legacy_payload={"error": f"Missing required fields: {missing}"},
            status_code=400,
            message=f"Missing required fields: {missing}",
            error_code="MISSING_FIELDS",
        )

    try:
        amount = Decimal(str(payload["amount"]))
        expected_date = _parse_date_param(payload["expected_date"])
    except (ValueError, Exception) as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="INVALID_FIELD",
        )

    _doc, entry = create_receivable(
        user_id=user_id,
        description=payload["description"],
        amount=amount,
        expected_date=expected_date,
        category=payload.get("category"),
    )
    data = {"receivable": _serialise_entry(entry)}
    return compat_success_tuple(
        legacy_payload={"message": "Recebível criado com sucesso", **data},
        status_code=201,
        message="Recebível criado com sucesso",
        data=data,
    )


@fiscal_bp.route("/receivables/<entry_id>/receive", methods=["PATCH"])
@jwt_required()
def receive_receivable(entry_id: str) -> tuple[dict[str, Any], int]:
    """Mark a receivable entry as received."""
    user_id = str(current_user_id())
    payload = request.get_json(silent=True) or {}

    received_date_raw = payload.get("received_date")
    if not received_date_raw:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'received_date' is required"},
            status_code=400,
            message="Field 'received_date' is required",
            error_code="MISSING_RECEIVED_DATE",
        )

    try:
        received_date = _parse_date_param(received_date_raw)
        received_amount: Decimal | None = None
        if payload.get("received_amount") is not None:
            received_amount = Decimal(str(payload["received_amount"]))
    except ValueError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="INVALID_FIELD",
        )

    try:
        entry = mark_received(entry_id, user_id, received_date, received_amount)
    except ReceivableNotFoundError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=404,
            message=str(exc),
            error_code="NOT_FOUND",
        )
    except ReceivableAlreadySettledError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=409,
            message=str(exc),
            error_code="ALREADY_SETTLED",
        )

    data = {"receivable": _serialise_entry(entry)}
    return compat_success_tuple(
        legacy_payload={"message": "Recebível marcado como recebido", **data},
        status_code=200,
        message="Recebível marcado como recebido",
        data=data,
    )


@fiscal_bp.route("/receivables/<entry_id>", methods=["DELETE"])
@jwt_required()
def delete_receivable(entry_id: str) -> tuple[dict[str, Any], int]:
    """Cancel a receivable entry."""
    user_id = str(current_user_id())

    try:
        entry = cancel_receivable(entry_id, user_id)
    except ReceivableNotFoundError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=404,
            message=str(exc),
            error_code="NOT_FOUND",
        )
    except ReceivableAlreadySettledError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=409,
            message=str(exc),
            error_code="ALREADY_SETTLED",
        )

    data = {"receivable": _serialise_entry(entry)}
    return compat_success_tuple(
        legacy_payload={"message": "Recebível cancelado com sucesso", **data},
        status_code=200,
        message="Recebível cancelado com sucesso",
        data=data,
    )


@fiscal_bp.route("/receivables/summary", methods=["GET"])
@jwt_required()
def receivables_summary() -> tuple[dict[str, Any], int]:
    """Return revenue summary totals for the current user."""
    user_id = str(current_user_id())
    summary = get_revenue_summary(user_id)
    return compat_success_tuple(
        legacy_payload=summary,
        status_code=200,
        message="Resumo de receitas obtido com sucesso",
        data={"summary": summary},
    )


# ---------------------------------------------------------------------------
# Fiscal document endpoints
# ---------------------------------------------------------------------------


@fiscal_bp.route("/fiscal-documents", methods=["GET"])
@jwt_required()
def get_fiscal_documents() -> tuple[dict[str, Any], int]:
    """List fiscal documents for the current user."""
    user_id = str(current_user_id())
    doc_type = request.args.get("type")
    docs = list_fiscal_documents(user_id, doc_type=doc_type)
    serialised = [_serialise_document(d) for d in docs]
    data = {"fiscal_documents": serialised, "count": len(serialised)}
    return compat_success_tuple(
        legacy_payload=data,
        status_code=200,
        message="Documentos fiscais listados com sucesso",
        data=data,
    )


@fiscal_bp.route("/fiscal-documents", methods=["POST"])
@jwt_required()
def create_fiscal_document_endpoint() -> tuple[dict[str, Any], int]:
    """Create a new fiscal document record."""
    user_id = str(current_user_id())
    payload = request.get_json(silent=True) or {}

    required = ("type", "amount", "issued_at")
    missing = [f for f in required if not payload.get(f)]
    if missing:
        return compat_error_tuple(
            legacy_payload={"error": f"Missing required fields: {missing}"},
            status_code=400,
            message=f"Missing required fields: {missing}",
            error_code="MISSING_FIELDS",
        )

    try:
        amount = Decimal(str(payload["amount"]))
        issued_at = _parse_date_param(payload["issued_at"])
    except ValueError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="INVALID_FIELD",
        )

    try:
        doc = create_fiscal_document(
            user_id=user_id,
            doc_type=payload["type"],
            amount=amount,
            issued_at=issued_at,
            counterpart_name=payload.get("counterpart_name"),
            external_id=payload.get("external_id"),
            raw_data=payload.get("raw_data"),
        )
    except ValueError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="INVALID_TYPE",
        )

    data = {"fiscal_document": _serialise_document(doc)}
    return compat_success_tuple(
        legacy_payload={"message": "Documento fiscal criado com sucesso", **data},
        status_code=201,
        message="Documento fiscal criado com sucesso",
        data=data,
    )
