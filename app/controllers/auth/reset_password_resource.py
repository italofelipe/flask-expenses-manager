from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.schemas.auth_schema import ResetPasswordSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class ResetPasswordResource(MethodResource):
    @doc(
        summary="Redefinir senha",
        description=(
            "Redefine a senha de um usuário a partir de um token de recuperação."
        ),
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        requestBody=json_request_body(
            schema=ResetPasswordSchema,
            description="Token de recuperação e nova senha válida.",
            example={
                "token": "G9Q7zJ6lQ4Vwm6dXj6nQjzH8QqfUuBqbMTe4PmS7p8Q",
                "new_password": "NovaSenha@123",
            },
        ),
        responses={
            200: json_success_response(
                description="Senha redefinida com sucesso",
                message="Password updated successfully",
                data_example={},
            ),
            400: json_error_response(
                description="Token inválido, expirado ou payload inválido",
                message="Token inválido ou expirado",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            500: json_error_response(
                description="Erro interno ao redefinir senha",
                message="Password reset failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @use_kwargs(ResetPasswordSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        dependencies = get_auth_dependencies()
        token = str(kwargs["token"])
        new_password = str(kwargs["new_password"])

        try:
            new_password_hash = dependencies.hash_password(new_password)
            result = dependencies.reset_password(token, new_password_hash)
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
                "Password reset completion failed due to unexpected error."
            )
            return compat_error(
                legacy_payload={"message": "Password reset failed"},
                status_code=500,
                message="Password reset failed",
                error_code="INTERNAL_ERROR",
            )
