# mypy: disable-error-code=no-any-return

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.schemas.transaction_schema import TransactionSchema

from .dependencies import get_transaction_dependencies
from .openapi import TRANSACTION_UPDATE_DOC
from .utils import (
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
)


class TransactionUpdateMixin:
    """PUT behavior for transaction updates with ownership + validation guards."""

    @doc(**TRANSACTION_UPDATE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(TransactionSchema(partial=True), location="json")  # type: ignore[misc]
    def put(self, transaction_id: UUID, **kwargs: Any) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        dependencies = get_transaction_dependencies()
        service = dependencies.transaction_application_service_factory(user_uuid)
        try:
            updated_data = service.update_transaction(transaction_id, kwargs)
        except TransactionApplicationError as exc:
            return _compat_error(
                legacy_payload={"error": exc.message, "details": exc.details},
                status_code=exc.status_code,
                message=exc.message,
                error_code=exc.code,
                details=exc.details,
            )
        except Exception:
            return _internal_error_response(
                message="Erro ao atualizar transação",
                log_context="transaction.update_failed",
            )

        return _compat_success(
            legacy_payload={
                "message": "Transação atualizada com sucesso",
                "transaction": updated_data,
            },
            status_code=200,
            message="Transação atualizada com sucesso",
            data={"transaction": updated_data},
        )
