from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.email_confirmation_service import (
    EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
    EMAIL_CONFIRMATION_SUCCESS_MESSAGE,
)
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.schemas.auth_schema import ConfirmEmailSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class ConfirmEmailResource(MethodResource):
    @doc(
        summary="Confirmar conta",
        description="Confirma a conta do usuario a partir do token enviado por email.",
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        requestBody=json_request_body(
            schema=ConfirmEmailSchema,
            description="Token de confirmacao recebido por email.",
            example={"token": "G9Q7zJ6lQ4Vwm6dXj6nQjzH8QqfUuBqbMTe4PmS7p8Q"},
        ),
        responses={
            200: json_success_response(
                description="Email confirmado com sucesso",
                message=EMAIL_CONFIRMATION_SUCCESS_MESSAGE,
                data_example={},
            ),
            400: json_error_response(
                description="Token inválido, expirado ou payload inválido",
                message=EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            500: json_error_response(
                description="Erro interno ao confirmar email",
                message="Email confirmation failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @use_kwargs(ConfirmEmailSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        try:
            result = get_auth_dependencies().confirm_email(str(kwargs["token"]))
            if not result.ok:
                return compat_error(
                    legacy_payload={"message": result.message},
                    status_code=400,
                    message=result.message,
                    error_code="VALIDATION_ERROR",
                )
            return compat_success(
                legacy_payload={"message": result.message},
                status_code=200,
                message=result.message,
                data={},
            )
        except Exception:
            current_app.logger.exception(
                "Email confirmation failed due to unexpected error."
            )
            return compat_error(
                legacy_payload={"message": "Email confirmation failed"},
                status_code=500,
                message="Email confirmation failed",
                error_code="INTERNAL_ERROR",
            )
