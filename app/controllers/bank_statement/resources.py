from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request

from app.auth import current_user_id
from app.controllers.response_contract import compat_error_tuple, compat_success_tuple
from app.services.bank_import_service import (
    BankImportConfirmation,
    BankImportPreview,
    BankImportService,
)
from app.services.transaction_serialization import serialize_transaction_payload
from app.utils.typed_decorators import typed_jwt_required as jwt_required


def _build_service() -> BankImportService:
    return BankImportService(_current_user_id())


def _current_user_id() -> UUID:
    return current_user_id()


def _decode_uploaded_text() -> str:
    upload = request.files.get("file")
    if upload is None:
        raise ValueError("Field 'file' is required")

    raw = bytes(upload.read())
    if not raw:
        raise ValueError("Uploaded file is empty")

    for encoding in ("utf-8", "latin-1"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("Uploaded file must be a text-based OFX or CSV")


def _serialize_preview(preview: BankImportPreview) -> dict[str, Any]:
    entries = [
        {
            "external_id": entry.external_id,
            "date": entry.date,
            "description": entry.description,
            "amount": str(entry.amount),
            "transaction_type": entry.transaction_type,
            "bank_name": entry.bank_name,
            "is_duplicate": entry.is_duplicate,
            "duplicate_reason": entry.duplicate_reason,
        }
        for entry in preview.entries
    ]
    return {
        "bank_name": preview.bank_name,
        "entries": entries,
        "total_entries": preview.total_entries,
        "duplicate_entries": preview.duplicate_entries,
        "new_entries": preview.new_entries,
    }


def _serialize_confirmation(result: BankImportConfirmation) -> dict[str, Any]:
    return {
        "bank_name": result.bank_name,
        "month": result.month,
        "imported_count": result.imported_count,
        "skipped_duplicates": result.skipped_duplicates,
        "replaced_count": result.replaced_count,
        "transactions": [
            serialize_transaction_payload(transaction)
            for transaction in result.transactions
        ],
    }


@jwt_required()
def preview_bank_statement() -> tuple[dict[str, Any], int]:
    bank_name = (request.form.get("bank") or "").strip()
    if not bank_name:
        return compat_error_tuple(
            legacy_payload={"error": "Field 'bank' is required"},
            status_code=400,
            message="Field 'bank' is required",
            error_code="MISSING_BANK",
        )

    try:
        content = _decode_uploaded_text()
        preview = _build_service().build_preview(content=content, bank_name=bank_name)
    except ValueError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="BANK_IMPORT_PREVIEW_ERROR",
        )

    data = _serialize_preview(preview)
    return compat_success_tuple(
        legacy_payload={"message": "Preview gerado com sucesso", **data},
        status_code=200,
        message="Preview gerado com sucesso",
        data=data,
    )


@jwt_required()
def confirm_bank_statement() -> tuple[dict[str, Any], int]:
    payload = request.get_json(silent=True) or {}
    bank_name = str(payload.get("bank", "")).strip()
    month = str(payload.get("month", "")).strip()
    mode = str(payload.get("mode", "")).strip()
    transactions = payload.get("transactions", [])

    missing = [
        field_name
        for field_name, value in (
            ("bank", bank_name),
            ("month", month),
            ("mode", mode),
        )
        if not value
    ]
    if missing:
        missing_message = f"Missing required field(s): {', '.join(missing)}"
        return compat_error_tuple(
            legacy_payload={"error": missing_message},
            status_code=400,
            message=missing_message,
            error_code="BANK_IMPORT_CONFIRMATION_ERROR",
        )

    if not isinstance(transactions, list):
        return compat_error_tuple(
            legacy_payload={"error": "Field 'transactions' must be a list"},
            status_code=400,
            message="Field 'transactions' must be a list",
            error_code="BANK_IMPORT_CONFIRMATION_ERROR",
        )

    try:
        result = _build_service().confirm_import(
            bank_name=bank_name,
            month=month,
            mode=mode,
            selected_entries=transactions,
        )
    except ValueError as exc:
        return compat_error_tuple(
            legacy_payload={"error": str(exc)},
            status_code=400,
            message=str(exc),
            error_code="BANK_IMPORT_CONFIRMATION_ERROR",
        )

    data = _serialize_confirmation(result)
    return compat_success_tuple(
        legacy_payload={"message": "Importação confirmada com sucesso", **data},
        status_code=201,
        message="Importação confirmada com sucesso",
        data=data,
    )


__all__ = ["confirm_bank_statement", "preview_bank_statement"]
