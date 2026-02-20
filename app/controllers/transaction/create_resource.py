# mypy: disable-error-code=no-any-return

from __future__ import annotations

from typing import Any, cast
from uuid import UUID

from flask import Response
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.schemas.transaction_schema import TransactionSchema

from .dependencies import get_transaction_dependencies
from .openapi import TRANSACTION_CREATE_DOC
from .utils import (
    _build_installment_amounts,
    _compat_error,
    _compat_success,
    _guard_revoked_token,
    _internal_error_response,
)


def _compat_installment_amounts(total: Any, count: int) -> list[Any]:
    """
    Preserve legacy monkeypatch path on transaction.resources facade.

    Some regression tests and local debugging flows patch
    `app.controllers.transaction.resources._build_installment_amounts`.
    This resolver keeps that behavior while code is split by concern.
    """
    from . import resources as legacy_resources

    builder = getattr(
        legacy_resources,
        "_build_installment_amounts",
        _build_installment_amounts,
    )
    return builder(total, count)


class TransactionCreateMixin:
    """POST behavior for transaction creation (single and installments)."""

    @doc(**TRANSACTION_CREATE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(TransactionSchema, location="json")  # type: ignore[misc]
    def post(self, **kwargs: Any) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = UUID(get_jwt_identity())
        dependencies = get_transaction_dependencies()
        service = dependencies.transaction_application_service_factory(user_uuid)
        try:
            result = service.create_transaction(
                kwargs,
                installment_amount_builder=_compat_installment_amounts,
            )
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
                message="Erro ao criar transação",
                log_context="transaction.create_failed",
            )

        legacy_key = str(result["legacy_key"])
        items = cast(list[dict[str, Any]], result["items"])
        return _compat_success(
            legacy_payload={"message": result["message"], legacy_key: items},
            status_code=201,
            message=str(result["message"]),
            data={legacy_key: items},
        )
