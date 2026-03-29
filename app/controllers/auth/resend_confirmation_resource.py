from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.email_confirmation_service import (
    EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
)
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.schemas.auth_schema import ResendConfirmationSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class ResendConfirmationResource(MethodResource):
    @doc(
        summary="Reenviar confirmacao de conta",
        description=(
            "Reenvia o email de confirmacao da conta. A resposta e neutra para "
            "evitar enumeracao de contas."
        ),
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        requestBody=json_request_body(
            schema=ResendConfirmationSchema,
            description="Email da conta que deseja confirmar.",
            example={"email": "italo@auraxis.com.br"},
        ),
        responses={
            200: json_success_response(
                description="Solicitação recebida com resposta neutra",
                message=EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
                data_example={},
            ),
            400: json_error_response(
                description="Erro de validacao",
                message="Dados inválidos",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            500: json_error_response(
                description="Erro interno ao reenviar confirmacao",
                message="Email confirmation resend failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @use_kwargs(ResendConfirmationSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        try:
            result = get_auth_dependencies().resend_email_confirmation(
                str(kwargs["email"])
            )
            return compat_success(
                legacy_payload={"message": result.message},
                status_code=200,
                message=result.message,
                data={},
            )
        except Exception:
            current_app.logger.exception(
                "Email confirmation resend failed due to unexpected error."
            )
            return compat_error(
                legacy_payload={"message": "Email confirmation resend failed"},
                status_code=500,
                message="Email confirmation resend failed",
                error_code="INTERNAL_ERROR",
            )
