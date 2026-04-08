from __future__ import annotations

from uuid import UUID

from flask import Response
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.extensions.database import db
from app.models.transaction import Transaction
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .dependencies import get_transaction_dependencies
from .list_resources import (
    _handle_transaction_request,
)
from .openapi import (
    TRANSACTION_DETAIL_DOC,
    TRANSACTION_FORCE_DELETE_DOC,
    TRANSACTION_RESTORE_DOC,
)
from .utils import (
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
)

__all__ = [
    "TransactionDetailResource",
    "TransactionForceDeleteResource",
    "TransactionRestoreResource",
    "_build_transaction_detail_response",
    "_handle_transaction_detail_request",
]


def _build_transaction_detail_response(
    *,
    user_uuid: UUID,
    transaction_id: UUID,
) -> Response:
    dependencies = get_transaction_dependencies()
    query_service = dependencies.transaction_query_service_factory(user_uuid)
    serialized = query_service.get_transaction(transaction_id)
    return _compat_success(
        legacy_payload={"transaction": serialized},
        status_code=200,
        message="Detalhe da transação carregado com sucesso",
        data={"transaction": serialized},
    )


def _handle_transaction_detail_request(*, transaction_id: UUID) -> Response:
    return _handle_transaction_request(
        builder=lambda user_uuid: _build_transaction_detail_response(
            user_uuid=user_uuid,
            transaction_id=transaction_id,
        ),
        internal_error_message="Erro ao buscar detalhe da transação",
        log_context="transaction.detail_failed",
    )


class TransactionDetailResource(MethodResource):
    @doc(**TRANSACTION_DETAIL_DOC)
    @jwt_required()
    def get(self, transaction_id: UUID) -> Response:
        return _handle_transaction_detail_request(transaction_id=transaction_id)


class TransactionForceDeleteResource(MethodResource):
    @doc(**TRANSACTION_FORCE_DELETE_DOC)
    @jwt_required()
    def delete(self, transaction_id: UUID) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = current_user_id()
        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=user_id, deleted=True
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


class TransactionRestoreResource(MethodResource):
    @doc(**TRANSACTION_RESTORE_DOC)
    @jwt_required()
    def patch(self, transaction_id: UUID) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
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
