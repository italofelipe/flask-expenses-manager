# mypy: disable-error-code=no-any-return

from __future__ import annotations

from uuid import UUID

from flask import Response
from flask_apispec import doc
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions.database import db
from app.models.transaction import Transaction

from .openapi import TRANSACTION_SOFT_DELETE_DOC
from .utils import (
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
)


class TransactionDeleteMixin:
    """DELETE behavior for transaction soft delete."""

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
