from __future__ import annotations

from uuid import UUID

from flask import Response, request
from flask_apispec import doc
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.application.services.public_error_mapper_service import (
    map_validation_exception,
)
from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.utils.pagination import PaginatedResponse

from .openapi import (
    TRANSACTION_ACTIVE_LIST_DOC,
    TRANSACTION_DASHBOARD_DOC,
    TRANSACTION_DELETED_LIST_DOC,
    TRANSACTION_EXPENSE_PERIOD_DOC,
    TRANSACTION_FORCE_DELETE_DOC,
    TRANSACTION_RESTORE_DOC,
    TRANSACTION_SUMMARY_DOC,
)
from .utils import (
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
    _parse_month_param,
    _parse_optional_date,
    _parse_optional_uuid,
    _parse_positive_int,
    _resolve_transaction_ordering,
    serialize_transaction,
)


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


class TransactionSummaryResource(MethodResource):
    @doc(**TRANSACTION_SUMMARY_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        try:
            year, month_number, month = _parse_month_param(request.args.get("month"))
            analytics = TransactionAnalyticsService(user_uuid)
            transactions = analytics.get_month_transactions(
                year=year, month_number=month_number
            )
            aggregates = analytics.get_month_aggregates(
                year=year, month_number=month_number
            )

            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            serialized = [serialize_transaction(item) for item in transactions]
            paginated = PaginatedResponse.format(
                serialized, len(transactions), page, page_size
            )

            return _compat_success(
                legacy_payload={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
                    **paginated,
                },
                status_code=200,
                message="Resumo mensal calculado com sucesso",
                data={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
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
    @doc(**TRANSACTION_DASHBOARD_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        try:
            year, month_number, month = _parse_month_param(request.args.get("month"))
            analytics = TransactionAnalyticsService(user_uuid)
            aggregates = analytics.get_month_aggregates(
                year=year, month_number=month_number
            )
            status_counts = analytics.get_status_counts(
                year=year, month_number=month_number
            )
            top_expense_categories = analytics.get_top_categories(
                year=year,
                month_number=month_number,
                transaction_type=TransactionType.EXPENSE,
            )
            top_income_categories = analytics.get_top_categories(
                year=year,
                month_number=month_number,
                transaction_type=TransactionType.INCOME,
            )

            return _compat_success(
                legacy_payload={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
                    "balance": float(aggregates["balance"]),
                    "counts": {
                        "total_transactions": aggregates["total_transactions"],
                        "income_transactions": aggregates["income_transactions"],
                        "expense_transactions": aggregates["expense_transactions"],
                        "status": status_counts,
                    },
                    "top_expense_categories": top_expense_categories,
                    "top_income_categories": top_income_categories,
                },
                status_code=200,
                message="Dashboard mensal calculado com sucesso",
                data={
                    "month": month,
                    "totals": {
                        "income_total": float(aggregates["income_total"]),
                        "expense_total": float(aggregates["expense_total"]),
                        "balance": float(aggregates["balance"]),
                    },
                    "counts": {
                        "total_transactions": aggregates["total_transactions"],
                        "income_transactions": aggregates["income_transactions"],
                        "expense_transactions": aggregates["expense_transactions"],
                        "status": status_counts,
                    },
                    "top_categories": {
                        "expense": top_expense_categories,
                        "income": top_income_categories,
                    },
                },
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


class TransactionForceDeleteResource(MethodResource):
    @doc(**TRANSACTION_FORCE_DELETE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def delete(self, transaction_id: UUID) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=UUID(user_id), deleted=True
        ).first()

        if not transaction:
            return _compat_error(
                legacy_payload={
                    "error": "Transação não encontrada ou não está deletada."
                },
                status_code=404,
                message="Transação não encontrada ou não está deletada.",
                error_code="NOT_FOUND",
            )

        try:
            db.session.delete(transaction)
            db.session.commit()
            return _compat_success(
                legacy_payload={"message": "Transação removida permanentemente."},
                status_code=200,
                message="Transação removida permanentemente.",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao deletar permanentemente",
                log_context="transaction.force_delete_failed",
            )


class TransactionExpensePeriodResource(MethodResource):
    @doc(**TRANSACTION_EXPENSE_PERIOD_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())

        try:
            start_date = _parse_optional_date(
                request.args.get("startDate"), "startDate"
            )
            final_date = _parse_optional_date(
                request.args.get("finalDate"), "finalDate"
            )
            if not start_date and not final_date:
                missing_date_error = (
                    "Informe ao menos um parâmetro: 'startDate' ou 'finalDate'."
                )
                return _compat_error(
                    legacy_payload={"error": missing_date_error},
                    status_code=400,
                    message=missing_date_error,
                    error_code="VALIDATION_ERROR",
                )

            if start_date and final_date and start_date > final_date:
                invalid_range_error = (
                    "Parâmetro 'startDate' não pode ser maior que 'finalDate'."
                )
                return _compat_error(
                    legacy_payload={"error": invalid_range_error},
                    status_code=400,
                    message=invalid_range_error,
                    error_code="VALIDATION_ERROR",
                )

            page = _parse_positive_int(
                request.args.get("page"), default=1, field_name="page"
            )
            per_page = _parse_positive_int(
                request.args.get("per_page"), default=10, field_name="per_page"
            )
            order_by = str(request.args.get("order_by", "due_date")).strip().lower()
            order = str(request.args.get("order", "desc")).strip().lower()
            ordering_clause = _resolve_transaction_ordering(order_by, order)

            base_query = Transaction.query.filter_by(user_id=user_uuid, deleted=False)
            if start_date:
                base_query = base_query.filter(Transaction.due_date >= start_date)
            if final_date:
                base_query = base_query.filter(Transaction.due_date <= final_date)

            total_transactions = base_query.count()
            income_transactions = base_query.filter(
                Transaction.type == TransactionType.INCOME
            ).count()
            expense_transactions = base_query.filter(
                Transaction.type == TransactionType.EXPENSE
            ).count()

            expenses_query = base_query.filter(
                Transaction.type == TransactionType.EXPENSE
            )
            total_expenses = expense_transactions
            pages = (total_expenses + per_page - 1) // per_page if total_expenses else 0
            expenses = (
                expenses_query.order_by(ordering_clause)
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            serialized_expenses = [serialize_transaction(item) for item in expenses]

            counts_payload = {
                "total_transactions": total_transactions,
                "income_transactions": income_transactions,
                "expense_transactions": expense_transactions,
            }

            return _compat_success(
                legacy_payload={
                    "expenses": serialized_expenses,
                    "total": total_expenses,
                    "page": page,
                    "per_page": per_page,
                    "counts": counts_payload,
                },
                status_code=200,
                message="Lista de despesas por período",
                data={"expenses": serialized_expenses, "counts": counts_payload},
                meta={
                    "pagination": {
                        "total": total_expenses,
                        "page": page,
                        "per_page": per_page,
                        "pages": pages,
                    }
                },
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetros de período inválidos.",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar despesas por período",
                log_context="transaction.expenses_period_failed",
            )


class TransactionDeletedResource(MethodResource):
    @doc(**TRANSACTION_DELETED_LIST_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        try:
            transactions = Transaction.query.filter_by(
                user_id=user_uuid, deleted=True
            ).all()
            serialized = [serialize_transaction(item) for item in transactions]
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


class TransactionRestoreResource(MethodResource):
    @doc(**TRANSACTION_RESTORE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def patch(self, transaction_id: UUID) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=user_uuid, deleted=True
        ).first()
        if transaction is None:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        try:
            transaction.deleted = False
            db.session.commit()
            return _compat_success(
                legacy_payload={"message": "Transação restaurada com sucesso"},
                status_code=200,
                message="Transação restaurada com sucesso",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao restaurar transação",
                log_context="transaction.restore_failed",
            )


class TransactionListActiveResource(MethodResource):
    @doc(**TRANSACTION_ACTIVE_LIST_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:  # noqa: C901
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        try:
            page = _parse_positive_int(
                request.args.get("page"), default=1, field_name="page"
            )
            per_page = _parse_positive_int(
                request.args.get("per_page"), default=10, field_name="per_page"
            )

            transaction_type = request.args.get("type")
            status = request.args.get("status")
            start_date = _parse_optional_date(
                request.args.get("start_date"), "start_date"
            )
            end_date = _parse_optional_date(request.args.get("end_date"), "end_date")
            tag_id = _parse_optional_uuid(request.args.get("tag_id"), "tag_id")
            account_id = _parse_optional_uuid(
                request.args.get("account_id"), "account_id"
            )
            credit_card_id = _parse_optional_uuid(
                request.args.get("credit_card_id"), "credit_card_id"
            )

            if start_date and end_date and start_date > end_date:
                start_date_error = (
                    "Parâmetro 'start_date' não pode ser maior que 'end_date'."
                )
                return _compat_error(
                    legacy_payload={"error": start_date_error},
                    status_code=400,
                    message=start_date_error,
                    error_code="VALIDATION_ERROR",
                )

            query = Transaction.query.filter_by(user_id=user_uuid, deleted=False)
            if transaction_type:
                try:
                    query = query.filter(
                        Transaction.type == TransactionType(transaction_type.lower())
                    )
                except ValueError:
                    type_error = "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
                    return _compat_error(
                        legacy_payload={"error": type_error},
                        status_code=400,
                        message=type_error,
                        error_code="VALIDATION_ERROR",
                    )
            if status:
                try:
                    query = query.filter(
                        Transaction.status == TransactionStatus(status.lower())
                    )
                except ValueError:
                    status_error = (
                        "Parâmetro 'status' inválido. "
                        "Use paid, pending, cancelled, postponed ou overdue."
                    )
                    return _compat_error(
                        legacy_payload={"error": status_error},
                        status_code=400,
                        message=status_error,
                        error_code="VALIDATION_ERROR",
                    )

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

            total = query.count()
            pages = (total + per_page - 1) // per_page if total else 0
            transactions = (
                query.order_by(
                    Transaction.due_date.desc(), Transaction.created_at.desc()
                )
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            serialized = [serialize_transaction(item) for item in transactions]
            return _compat_success(
                legacy_payload={
                    "transactions": serialized,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                },
                status_code=200,
                message="Lista de transações ativas",
                data={"transactions": serialized},
                meta={
                    "pagination": {
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "pages": pages,
                    }
                },
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetros de listagem inválidos.",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar transações ativas",
                log_context="transaction.list_active_failed",
            )


__all__ = [
    "TransactionSummaryResource",
    "TransactionMonthlyDashboardResource",
    "TransactionForceDeleteResource",
    "TransactionExpensePeriodResource",
    "TransactionDeletedResource",
    "TransactionRestoreResource",
    "TransactionListActiveResource",
    "_guard_revoked_token",
    "_resolve_transaction_ordering",
    "TransactionAnalyticsService",
]
