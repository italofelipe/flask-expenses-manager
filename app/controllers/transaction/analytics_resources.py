from __future__ import annotations

from typing import Any

from flask import Response, request
from flask_apispec.views import MethodResource

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.auth import current_user_id
from app.extensions.database import db
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .dependencies import get_transaction_dependencies
from .list_resources import (
    _first_query_value,
    _validation_error_response,
)
from .openapi import (
    TRANSACTION_DASHBOARD_DOC,
    TRANSACTION_DELETED_LIST_DOC,
    TRANSACTION_DUE_PERIOD_DOC,
    TRANSACTION_EXPENSE_PERIOD_DOC,
    TRANSACTION_SUMMARY_DOC,
)
from .utils import (
    _apply_deprecation_headers,
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
    _parse_optional_date,
    _parse_positive_int,
    _resolve_transaction_ordering,
)

__all__ = [
    "TransactionSummaryResource",
    "TransactionMonthlyDashboardResource",
    "TransactionExpensePeriodResource",
    "TransactionDeletedResource",
    "TransactionDuePeriodResource",
    "_parse_summary_pagination",
    "_parse_expense_period_params",
    "_parse_due_range_params",
    "_deprecated_expense_alias_response",
    "_deprecated_dashboard_alias_response",
]


def _parse_summary_pagination() -> tuple[int, int]:
    page = _parse_positive_int(request.args.get("page"), default=1, field_name="page")
    per_page = _parse_positive_int(
        _first_query_value("per_page", "page_size"),
        default=10,
        field_name="per_page",
    )
    return page, per_page


def _parse_expense_period_params() -> dict[str, Any]:
    start_date = _parse_optional_date(
        _first_query_value("start_date", "startDate"),
        "start_date",
    )
    end_date = _parse_optional_date(
        _first_query_value("end_date", "finalDate"),
        "end_date",
    )
    return {
        "start_date": start_date,
        "end_date": end_date,
        "page": _parse_positive_int(
            request.args.get("page"), default=1, field_name="page"
        ),
        "per_page": _parse_positive_int(
            request.args.get("per_page"), default=10, field_name="per_page"
        ),
        "order_by": str(request.args.get("order_by", "due_date")).strip().lower(),
        "order": str(request.args.get("order", "desc")).strip().lower(),
    }


def _parse_due_range_params() -> dict[str, Any]:
    return {
        "start_date": _first_query_value("start_date", "initialDate"),
        "end_date": _first_query_value("end_date", "finalDate"),
        "page": _parse_positive_int(
            request.args.get("page"), default=1, field_name="page"
        ),
        "per_page": _parse_positive_int(
            request.args.get("per_page"), default=10, field_name="per_page"
        ),
        "order_by": str(request.args.get("order_by", "overdue_first")).strip().lower(),
    }


def _deprecated_expense_alias_response(response: Response) -> Response:
    return _apply_deprecation_headers(
        response,
        successor_endpoint="/transactions?type=expense",
        successor_method="GET",
    )


def _deprecated_dashboard_alias_response(response: Response) -> Response:
    return _apply_deprecation_headers(
        response,
        successor_endpoint="/dashboard/overview",
        successor_method="GET",
    )


class TransactionSummaryResource(MethodResource):
    @doc(**TRANSACTION_SUMMARY_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        try:
            page, per_page = _parse_summary_pagination()
            dependencies = get_transaction_dependencies()
            query_service = dependencies.transaction_query_service_factory(user_uuid)
            result = query_service.get_month_summary(
                month=str(request.args.get("month", "")),
                page=page,
                per_page=per_page,
            )
            paginated = result["paginated"]

            return _compat_success(
                legacy_payload={
                    "month": result["month"],
                    "income_total": result["income_total"],
                    "expense_total": result["expense_total"],
                    **paginated,
                },
                status_code=200,
                message="Resumo mensal calculado com sucesso",
                data={
                    "month": result["month"],
                    "income_total": result["income_total"],
                    "expense_total": result["expense_total"],
                    "items": paginated["data"],
                },
                meta={
                    "pagination": {
                        "total": paginated["total"],
                        "page": paginated["page"],
                        "per_page": paginated["page_size"],
                        "has_next_page": paginated["has_next_page"],
                    }
                },
            )
        except TransactionApplicationError as exc:
            return _compat_error(
                legacy_payload={"error": exc.message, "details": exc.details},
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.code,
                details=exc.details,
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetro de mês inválido.",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao calcular resumo mensal",
                log_context="transaction.monthly_summary_failed",
            )


class TransactionMonthlyDashboardResource(MethodResource):
    @doc(**TRANSACTION_DASHBOARD_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        try:
            dependencies = get_transaction_dependencies()
            query_service = dependencies.transaction_query_service_factory(user_uuid)
            result = query_service.get_dashboard_overview(
                month=str(request.args.get("month", "")),
            )

            return _deprecated_dashboard_alias_response(
                _compat_success(
                    legacy_payload={
                        "month": result["month"],
                        "income_total": result["income_total"],
                        "expense_total": result["expense_total"],
                        "balance": result["balance"],
                        "counts": result["counts"],
                        "top_expense_categories": result["top_expense_categories"],
                        "top_income_categories": result["top_income_categories"],
                    },
                    status_code=200,
                    message="Dashboard mensal calculado com sucesso",
                    data={
                        "month": result["month"],
                        "totals": {
                            "income_total": result["income_total"],
                            "expense_total": result["expense_total"],
                            "balance": result["balance"],
                        },
                        "counts": result["counts"],
                        "top_categories": {
                            "expense": result["top_expense_categories"],
                            "income": result["top_income_categories"],
                        },
                    },
                )
            )
        except TransactionApplicationError as exc:
            return _compat_error(
                legacy_payload={"error": exc.message, "details": exc.details},
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.code,
                details=exc.details,
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetro de mês inválido.",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao calcular dashboard mensal",
                log_context="transaction.monthly_dashboard_failed",
            )


class TransactionExpensePeriodResource(MethodResource):
    @doc(**TRANSACTION_EXPENSE_PERIOD_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()

        try:
            params = _parse_expense_period_params()
            start_date = params["start_date"]
            end_date = params["end_date"]
            if not start_date and not end_date:
                missing_date_error = (
                    "Informe ao menos um parâmetro: 'start_date' ou 'end_date'."
                )
                return _deprecated_expense_alias_response(
                    _compat_error(
                        legacy_payload={"error": missing_date_error},
                        status_code=400,
                        message=missing_date_error,
                        error_code="VALIDATION_ERROR",
                    )
                )

            if start_date and end_date and start_date > end_date:
                invalid_range_error = (
                    "Parâmetro 'start_date' não pode ser maior que 'end_date'."
                )
                return _deprecated_expense_alias_response(
                    _compat_error(
                        legacy_payload={"error": invalid_range_error},
                        status_code=400,
                        message=invalid_range_error,
                        error_code="VALIDATION_ERROR",
                    )
                )

            page = params["page"]
            per_page = params["per_page"]
            order_by = params["order_by"]
            order = params["order"]
            ordering_clause = _resolve_transaction_ordering(order_by, order)
            dependencies = get_transaction_dependencies()
            query_service = dependencies.transaction_query_service_factory(user_uuid)
            result = query_service.get_expense_period(
                start_date=start_date,
                end_date=end_date,
                page=page,
                per_page=per_page,
                ordering_clause=ordering_clause,
            )
            serialized_expenses = result["expenses"]
            counts_payload = result["counts"]
            pagination = result["pagination"]

            response = _compat_success(
                legacy_payload={
                    "expenses": serialized_expenses,
                    "total": pagination["total"],
                    "page": page,
                    "per_page": per_page,
                    "counts": counts_payload,
                },
                status_code=200,
                message="Lista de despesas por período",
                data={"expenses": serialized_expenses, "counts": counts_payload},
                meta={
                    "pagination": {
                        "total": pagination["total"],
                        "page": page,
                        "per_page": per_page,
                        "pages": pagination["pages"],
                    }
                },
            )
            return _deprecated_expense_alias_response(response)
        except ValueError as exc:
            return _deprecated_expense_alias_response(
                _validation_error_response(
                    exc=exc,
                    fallback_message="Parâmetros de período inválidos.",
                )
            )
        except Exception:
            db.session.rollback()
            return _deprecated_expense_alias_response(
                _internal_error_response(
                    message="Erro ao buscar despesas por período",
                    log_context="transaction.expenses_period_failed",
                )
            )


class TransactionDeletedResource(MethodResource):
    @doc(**TRANSACTION_DELETED_LIST_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        try:
            dependencies = get_transaction_dependencies()
            query_service = dependencies.transaction_query_service_factory(user_uuid)
            serialized = query_service.list_deleted_transactions()
            return _compat_success(
                legacy_payload={"deleted_transactions": serialized},
                status_code=200,
                message="Lista de transações deletadas",
                data={"deleted_transactions": serialized},
                meta={"total": len(serialized)},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar transações deletadas",
                log_context="transaction.list_deleted_failed",
            )


class TransactionDuePeriodResource(MethodResource):
    @doc(**TRANSACTION_DUE_PERIOD_DOC)
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        try:
            params = _parse_due_range_params()

            dependencies = get_transaction_dependencies()
            query_service = dependencies.transaction_query_service_factory(user_uuid)
            result = query_service.get_due_transactions(
                start_date=params["start_date"],
                end_date=params["end_date"],
                page=params["page"],
                per_page=params["per_page"],
                order_by=params["order_by"],
            )
            pagination = result["pagination"]
            counts = result["counts"]

            return _compat_success(
                legacy_payload={
                    "transactions": result["items"],
                    "total": pagination["total"],
                    "page": pagination["page"],
                    "per_page": pagination["per_page"],
                    "counts": counts,
                },
                status_code=200,
                message="Lista de vencimentos por período",
                data={"transactions": result["items"], "counts": counts},
                meta={
                    "pagination": {
                        "total": pagination["total"],
                        "page": pagination["page"],
                        "per_page": pagination["per_page"],
                        "pages": pagination["pages"],
                    }
                },
            )
        except TransactionApplicationError as exc:
            return _compat_error(
                legacy_payload={"error": exc.message, "details": exc.details},
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.code,
                details=exc.details,
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetros de vencimentos inválidos.",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar vencimentos por período",
                log_context="transaction.due_period_failed",
            )
