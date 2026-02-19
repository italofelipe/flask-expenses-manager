# mypy: disable-error-code=no-any-return

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions.database import db
from app.models.transaction import Transaction
from app.schemas.transaction_schema import TransactionSchema
from app.utils.datetime_utils import utc_now_compatible_with

from .openapi import TRANSACTION_UPDATE_DOC
from .utils import (
    _apply_transaction_updates,
    _compat_error,
    _compat_success,
    _enforce_transaction_reference_ownership_or_error,
    _guard_revoked_token,
    _internal_error_response,
    _validate_recurring_payload,
    serialize_transaction,
)


class TransactionUpdateMixin:
    """PUT behavior for transaction updates with ownership + validation guards."""

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
