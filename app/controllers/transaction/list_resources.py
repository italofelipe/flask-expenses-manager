from __future__ import annotations

from collections.abc import Callable
from typing import Any
from uuid import UUID

from flask import Response, request
from flask_apispec.views import MethodResource

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.auth import current_user_id
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .dependencies import get_transaction_dependencies
from .openapi import (
    TRANSACTION_ACTIVE_LIST_DOC,
    TRANSACTION_ACTIVE_LIST_LEGACY_DOC,
)
from .utils import (
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
    _parse_optional_date,
    _parse_optional_uuid,
    _parse_positive_int,
    _resolve_transaction_ordering,
)

# Re-export utils symbols so analytics/detail modules can import them from here
# and so report_resources.py can re-export them in __all__.
__all__ = [
    "TransactionCollectionResource",
    "TransactionListActiveResource",
    "_validation_error_response",
    "_first_query_value",
    "_parse_active_list_query_params",
    "_active_list_date_range_error",
    "_apply_active_list_type_filter",
    "_apply_active_list_status_filter",
    "_apply_active_list_optional_filters",
    "_build_active_list_response",
    "_handle_transaction_request",
    "_handle_active_transactions_request",
    "_guard_revoked_token",
    "_resolve_transaction_ordering",
]


def _validation_error_response(
    *,
    exc: Exception,
    fallback_message: str,
) -> Response:
    mapped_error = map_validation_exception(exc, fallback_message=fallback_message)
    return _compat_error(
        legacy_payload={"error": mapped_error.message},
        status_code=mapped_error.status_code,
        message=mapped_error.message,
        error_code=mapped_error.code,
        details=mapped_error.details,
    )


def _first_query_value(*names: str) -> str | None:
    for name in names:
        value = request.args.get(name)
        if value is not None:
            return str(value)
    return None


def _parse_active_list_query_params() -> dict[str, Any]:
    return {
        "page": _parse_positive_int(
            request.args.get("page"), default=1, field_name="page"
        ),
        "per_page": _parse_positive_int(
            request.args.get("per_page"),
            default=10,
            field_name="per_page",
        ),
        "transaction_type": request.args.get("type"),
        "status": request.args.get("status"),
        "start_date": _parse_optional_date(
            request.args.get("start_date"), "start_date"
        ),
        "end_date": _parse_optional_date(request.args.get("end_date"), "end_date"),
        "tag_id": _parse_optional_uuid(request.args.get("tag_id"), "tag_id"),
        "account_id": _parse_optional_uuid(
            request.args.get("account_id"), "account_id"
        ),
        "credit_card_id": _parse_optional_uuid(
            request.args.get("credit_card_id"), "credit_card_id"
        ),
    }


def _active_list_date_range_error(*, start_date: Any, end_date: Any) -> Response | None:
    if not start_date or not end_date or start_date <= end_date:
        return None
    message = "Parâmetro 'start_date' não pode ser maior que 'end_date'."
    return _compat_error(
        legacy_payload={"error": message},
        status_code=400,
        message=message,
        error_code="VALIDATION_ERROR",
    )


def _apply_active_list_type_filter(
    query: Any, transaction_type: str | None
) -> tuple[Any, Response | None]:
    if not transaction_type:
        return query, None
    try:
        return (
            query.filter(Transaction.type == TransactionType(transaction_type.lower())),
            None,
        )
    except ValueError:
        message = "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
        return query, _compat_error(
            legacy_payload={"error": message},
            status_code=400,
            message=message,
            error_code="VALIDATION_ERROR",
        )


def _apply_active_list_status_filter(
    query: Any, status: str | None
) -> tuple[Any, Response | None]:
    if not status:
        return query, None
    try:
        return (
            query.filter(Transaction.status == TransactionStatus(status.lower())),
            None,
        )
    except ValueError:
        message = (
            "Parâmetro 'status' inválido. "
            "Use paid, pending, cancelled, postponed ou overdue."
        )
        return query, _compat_error(
            legacy_payload={"error": message},
            status_code=400,
            message=message,
            error_code="VALIDATION_ERROR",
        )


def _apply_active_list_optional_filters(
    query: Any,
    *,
    start_date: Any,
    end_date: Any,
    tag_id: Any,
    account_id: Any,
    credit_card_id: Any,
) -> Any:
    if start_date:
        query = query.filter(Transaction.due_date >= start_date)
    if end_date:
        query = query.filter(Transaction.due_date <= end_date)
    if tag_id:
        query = query.filter(Transaction.tag_id == tag_id)
    if account_id:
        query = query.filter(Transaction.account_id == account_id)
    if credit_card_id:
        query = query.filter(Transaction.credit_card_id == credit_card_id)
    return query


def _build_active_list_response(user_uuid: UUID) -> Response:
    params = _parse_active_list_query_params()
    range_error = _active_list_date_range_error(
        start_date=params["start_date"],
        end_date=params["end_date"],
    )
    if range_error is not None:
        return range_error

    dependencies = get_transaction_dependencies()
    query_service = dependencies.transaction_query_service_factory(user_uuid)
    result = query_service.get_active_transactions(
        page=params["page"],
        per_page=params["per_page"],
        transaction_type=params["transaction_type"],
        status=params["status"],
        start_date=params["start_date"],
        end_date=params["end_date"],
        tag_id=params["tag_id"],
        account_id=params["account_id"],
        credit_card_id=params["credit_card_id"],
    )
    pagination = result["pagination"]
    serialized = result["items"]
    return _compat_success(
        legacy_payload={
            "transactions": serialized,
            "total": pagination["total"],
            "page": pagination["page"],
            "per_page": pagination["per_page"],
        },
        status_code=200,
        message="Lista de transações ativas",
        data={"transactions": serialized},
        meta={"pagination": pagination},
    )


def _handle_transaction_request(
    *,
    builder: Callable[[UUID], Response],
    internal_error_message: str,
    log_context: str,
    validation_error_message: str | None = None,
) -> Response:
    token_error = _guard_revoked_token()
    if token_error is not None:
        return token_error

    user_uuid = current_user_id()
    try:
        return builder(user_uuid)
    except TransactionApplicationError as exc:
        return _compat_error(
            legacy_payload={"error": exc.message, "details": exc.details},
            status_code=exc.status_code,
            message=exc.message,
            error_code=exc.code,
            details=exc.details,
        )
    except ValueError as exc:
        if validation_error_message is None:
            raise
        return _validation_error_response(
            exc=exc,
            fallback_message=validation_error_message,
        )
    except Exception:
        db.session.rollback()
        return _internal_error_response(
            message=internal_error_message,
            log_context=log_context,
        )


def _handle_active_transactions_request() -> Response:
    return _handle_transaction_request(
        builder=_build_active_list_response,
        internal_error_message="Erro ao buscar transações ativas",
        log_context="transaction.list_active_failed",
        validation_error_message="Parâmetros de listagem inválidos.",
    )


class TransactionCollectionResource(MethodResource):
    @doc(**TRANSACTION_ACTIVE_LIST_DOC)
    @jwt_required()
    def get(self) -> Response:
        return _handle_active_transactions_request()


class TransactionListActiveResource(MethodResource):
    @doc(**TRANSACTION_ACTIVE_LIST_LEGACY_DOC)
    @jwt_required()
    def get(self) -> Response:
        return _handle_active_transactions_request()
