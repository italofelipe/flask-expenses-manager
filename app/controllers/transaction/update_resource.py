# mypy: disable-error-code=no-any-return

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.auth import current_user_id
from app.schemas.transaction_schema import TransactionSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .dependencies import get_transaction_dependencies
from .openapi import TRANSACTION_UPDATE_PATCH_DOC, TRANSACTION_UPDATE_PUT_COMPAT_DOC
from .utils import (
    _apply_deprecation_headers,
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
)


class TransactionUpdateMixin:
    """PATCH/PUT behavior for transaction updates with ownership guards."""

    def _update_transaction(
        self, transaction_id: UUID, payload: dict[str, Any]
    ) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        dependencies = get_transaction_dependencies()
        service = dependencies.transaction_application_service_factory(user_uuid)
        try:
            updated_data = service.update_transaction(transaction_id, payload)
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

    @doc(**TRANSACTION_UPDATE_PATCH_DOC)
    @jwt_required()
    @use_kwargs(TransactionSchema(partial=True), location="json")
    def patch(self, transaction_id: UUID, **kwargs: Any) -> Response:
        return self._update_transaction(transaction_id, kwargs)

    @doc(**TRANSACTION_UPDATE_PUT_COMPAT_DOC)
    @jwt_required()
    @use_kwargs(TransactionSchema(partial=True), location="json")
    def put(self, transaction_id: UUID, **kwargs: Any) -> Response:
        response = self._update_transaction(transaction_id, kwargs)
        return _apply_deprecation_headers(
            response,
            successor_endpoint="/transactions/{transaction_id}",
            successor_method="PATCH",
        )
