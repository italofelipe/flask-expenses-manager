# mypy: disable-error-code=no-any-return

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import Blueprint, Response
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)

from app.controllers.transaction_controller_utils import (
    _apply_transaction_updates,
    _build_installment_amounts,
    _compat_error,
    _compat_success,
    _enforce_transaction_reference_ownership_or_error,
    _internal_error_response,
    _invalid_token_response,
    _validate_recurring_payload,
    serialize_transaction,
)
from app.controllers.transaction_openapi import (
    TRANSACTION_CREATE_DOC,
    TRANSACTION_SOFT_DELETE_DOC,
    TRANSACTION_UPDATE_DOC,
)
from app.controllers.transaction_report_resources import (
    TransactionDeletedResource,
    TransactionExpensePeriodResource,
    TransactionForceDeleteResource,
    TransactionListActiveResource,
    TransactionMonthlyDashboardResource,
    TransactionRestoreResource,
    TransactionSummaryResource,
)
from app.extensions.database import db
from app.extensions.jwt_callbacks import is_token_revoked
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.schemas.transaction_schema import TransactionSchema
from app.utils.datetime_utils import utc_now_compatible_with

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")


def _guard_revoked_token() -> Response | None:
    verify_jwt_in_request()
    jwt_data = get_jwt()
    if is_token_revoked(jwt_data["jti"]):
        return _invalid_token_response()
    return None


class TransactionResource(MethodResource):
    @doc(**TRANSACTION_CREATE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(TransactionSchema, location="json")  # type: ignore[misc]
    def post(self, **kwargs: Any) -> Response:  # noqa: C901
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].lower()

        recurring_error = _validate_recurring_payload(
            is_recurring=bool(kwargs.get("is_recurring", False)),
            due_date=kwargs.get("due_date"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        )
        if recurring_error:
            return _compat_error(
                legacy_payload={"error": recurring_error},
                status_code=400,
                message=recurring_error,
                error_code="VALIDATION_ERROR",
            )

        reference_error = _enforce_transaction_reference_ownership_or_error(
            user_id=user_uuid,
            tag_id=kwargs.get("tag_id"),
            account_id=kwargs.get("account_id"),
            credit_card_id=kwargs.get("credit_card_id"),
        )
        if reference_error:
            return _compat_error(
                legacy_payload={"error": reference_error},
                status_code=400,
                message=reference_error,
                error_code="VALIDATION_ERROR",
            )

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            from uuid import uuid4

            from dateutil.relativedelta import relativedelta

            try:
                group_id = uuid4()
                total = Decimal(kwargs["amount"])
                count = int(kwargs["installment_count"])
                base_date = kwargs["due_date"]
                installment_amounts = _build_installment_amounts(total, count)
                title = kwargs["title"]
                if "type" in kwargs:
                    kwargs["type"] = kwargs["type"].lower()

                transactions = []
                for i in range(count):
                    due = base_date + relativedelta(months=i)
                    transaction = Transaction(
                        user_id=user_uuid,
                        title=f"{title} ({i + 1}/{count})",
                        amount=installment_amounts[i],
                        type=TransactionType(kwargs["type"]),
                        due_date=due,
                        start_date=kwargs.get("start_date"),
                        end_date=kwargs.get("end_date"),
                        description=kwargs.get("description"),
                        observation=kwargs.get("observation"),
                        is_recurring=kwargs.get("is_recurring", False),
                        is_installment=True,
                        installment_count=count,
                        tag_id=kwargs.get("tag_id"),
                        account_id=kwargs.get("account_id"),
                        credit_card_id=kwargs.get("credit_card_id"),
                        status=TransactionStatus(
                            kwargs.get("status", "pending").lower()
                        ),
                        currency=kwargs.get("currency", "BRL"),
                        installment_group_id=group_id,
                    )
                    transactions.append(transaction)

                db.session.add_all(transactions)
                db.session.commit()

                created_data = [serialize_transaction(item) for item in transactions]
                return _compat_success(
                    legacy_payload={
                        "message": "Transações parceladas criadas com sucesso",
                        "transactions": created_data,
                    },
                    status_code=201,
                    message="Transações parceladas criadas com sucesso",
                    data={"transactions": created_data},
                )
            except Exception:
                db.session.rollback()
                return _internal_error_response(
                    message="Erro ao criar transações parceladas",
                    log_context="transaction.installment.create_failed",
                )

        try:
            transaction = Transaction(
                user_id=user_uuid,
                title=kwargs["title"],
                amount=kwargs["amount"],
                type=TransactionType(kwargs["type"]),
                due_date=kwargs["due_date"],
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                description=kwargs.get("description"),
                observation=kwargs.get("observation"),
                is_recurring=kwargs.get("is_recurring", False),
                is_installment=kwargs.get("is_installment", False),
                installment_count=kwargs.get("installment_count"),
                tag_id=kwargs.get("tag_id"),
                account_id=kwargs.get("account_id"),
                credit_card_id=kwargs.get("credit_card_id"),
                status=TransactionStatus(kwargs.get("status", "pending").lower()),
                currency=kwargs.get("currency", "BRL"),
            )

            db.session.add(transaction)
            db.session.commit()

            created_data = [serialize_transaction(transaction)]
            return _compat_success(
                legacy_payload={
                    "message": "Transação criada com sucesso",
                    "transaction": created_data,
                },
                status_code=201,
                message="Transação criada com sucesso",
                data={"transaction": created_data},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao criar transação",
                log_context="transaction.create_failed",
            )

    @doc(**TRANSACTION_UPDATE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(TransactionSchema(partial=True), location="json")  # type: ignore[misc]
    def put(self, transaction_id: UUID, **kwargs: Any) -> Response:  # noqa: C901
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

        if transaction is None:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        if str(transaction.user_id) != str(user_id):
            return _compat_error(
                legacy_payload={
                    "error": "Você não tem permissão para editar esta transação."
                },
                status_code=403,
                message="Você não tem permissão para editar esta transação.",
                error_code="FORBIDDEN",
            )

        if kwargs.get("type") is not None:
            kwargs["type"] = str(kwargs["type"]).lower()
        if kwargs.get("status") is not None:
            kwargs["status"] = str(kwargs["status"]).lower()

        if kwargs.get("status", "").lower() == "paid" and not kwargs.get("paid_at"):
            return _compat_error(
                legacy_payload={
                    "error": (
                        "É obrigatório informar 'paid_at' ao marcar a transação "
                        "como paga (status=PAID)."
                    )
                },
                status_code=400,
                message=(
                    "É obrigatório informar 'paid_at' ao marcar a transação "
                    "como paga (status=PAID)."
                ),
                error_code="VALIDATION_ERROR",
            )

        if kwargs.get("paid_at") and kwargs.get("status", "").lower() != "paid":
            return _compat_error(
                legacy_payload={
                    "error": "'paid_at' só pode ser definido se o status for 'PAID'."
                },
                status_code=400,
                message="'paid_at' só pode ser definido se o status for 'PAID'.",
                error_code="VALIDATION_ERROR",
            )

        if "paid_at" in kwargs and kwargs["paid_at"] is not None:
            if kwargs["paid_at"] > utc_now_compatible_with(kwargs["paid_at"]):
                return _compat_error(
                    legacy_payload={"error": "'paid_at' não pode ser uma data futura."},
                    status_code=400,
                    message="'paid_at' não pode ser uma data futura.",
                    error_code="VALIDATION_ERROR",
                )

        resolved_is_recurring = bool(
            kwargs.get("is_recurring", transaction.is_recurring)
        )
        resolved_due_date = kwargs.get("due_date", transaction.due_date)
        resolved_start_date = kwargs.get("start_date", transaction.start_date)
        resolved_end_date = kwargs.get("end_date", transaction.end_date)
        recurring_error = _validate_recurring_payload(
            is_recurring=resolved_is_recurring,
            due_date=resolved_due_date,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
        )
        if recurring_error:
            return _compat_error(
                legacy_payload={"error": recurring_error},
                status_code=400,
                message=recurring_error,
                error_code="VALIDATION_ERROR",
            )

        resolved_tag_id = kwargs["tag_id"] if "tag_id" in kwargs else transaction.tag_id
        resolved_account_id = (
            kwargs["account_id"] if "account_id" in kwargs else transaction.account_id
        )
        resolved_credit_card_id = (
            kwargs["credit_card_id"]
            if "credit_card_id" in kwargs
            else transaction.credit_card_id
        )
        reference_error = _enforce_transaction_reference_ownership_or_error(
            user_id=user_uuid,
            tag_id=resolved_tag_id,
            account_id=resolved_account_id,
            credit_card_id=resolved_credit_card_id,
        )
        if reference_error:
            return _compat_error(
                legacy_payload={"error": reference_error},
                status_code=400,
                message=reference_error,
                error_code="VALIDATION_ERROR",
            )

        try:
            _apply_transaction_updates(transaction, kwargs)
            db.session.commit()

            updated_data = serialize_transaction(transaction)
            return _compat_success(
                legacy_payload={
                    "message": "Transação atualizada com sucesso",
                    "transaction": updated_data,
                },
                status_code=200,
                message="Transação atualizada com sucesso",
                data={"transaction": updated_data},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao atualizar transação",
                log_context="transaction.update_failed",
            )

    @doc(**TRANSACTION_SOFT_DELETE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def delete(self, transaction_id: UUID) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

        if transaction is None:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        if str(transaction.user_id) != str(user_id):
            return _compat_error(
                legacy_payload={
                    "error": "Você não tem permissão para deletar esta transação."
                },
                status_code=403,
                message="Você não tem permissão para deletar esta transação.",
                error_code="FORBIDDEN",
            )

        try:
            transaction.deleted = True
            db.session.commit()

            return _compat_success(
                legacy_payload={
                    "message": "Transação deletada com sucesso (soft delete)."
                },
                status_code=200,
                message="Transação deletada com sucesso (soft delete).",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao deletar transação",
                log_context="transaction.soft_delete_failed",
            )


transaction_bp.add_url_rule(
    "", view_func=TransactionResource.as_view("transactionresource")
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transactionupdate"),
    methods=["PUT"],
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transactiondelete"),
    methods=["DELETE"],
)

transaction_bp.add_url_rule(
    "/restore/<uuid:transaction_id>",
    view_func=TransactionRestoreResource.as_view("transaction_restore"),
    methods=["PATCH"],
)

transaction_bp.add_url_rule(
    "/deleted",
    view_func=TransactionDeletedResource.as_view("transaction_list_deleted"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>/force",
    view_func=TransactionForceDeleteResource.as_view("transaction_delete_force"),
    methods=["DELETE"],
)

transaction_bp.add_url_rule(
    "/summary",
    view_func=TransactionSummaryResource.as_view("transaction_monthly_summary"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/dashboard",
    view_func=TransactionMonthlyDashboardResource.as_view(
        "transaction_monthly_dashboard"
    ),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/list",
    view_func=TransactionListActiveResource.as_view("transaction_list_active"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/expenses",
    view_func=TransactionExpensePeriodResource.as_view("transaction_expense_period"),
    methods=["GET"],
)
