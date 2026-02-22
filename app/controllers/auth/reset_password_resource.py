# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource

from app.schemas.auth_schema import ResetPasswordSchema

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class ResetPasswordResource(MethodResource):
    @doc(
        description=(
            "Redefine a senha de um usuário a partir de um token de recuperação."
        ),
        tags=["Autenticação"],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        requestBody={
            "required": True,
            "content": {
                "application/json": {
                    "schema": ResetPasswordSchema,
                    "example": {
                        "token": "G9Q7zJ6lQ4Vwm6dXj6nQjzH8QqfUuBqbMTe4PmS7p8Q",
                        "new_password": "NovaSenha@123",
                    },
                }
            },
        },
        responses={
            200: {"description": "Senha redefinida com sucesso"},
            400: {"description": "Token inválido/expirado ou payload inválido"},
            500: {"description": "Erro interno ao redefinir senha"},
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
