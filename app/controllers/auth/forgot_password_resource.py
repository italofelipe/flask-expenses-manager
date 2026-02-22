# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any

from flask import Response, current_app, request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource

from app.application.services.password_reset_service import (
    PASSWORD_RESET_NEUTRAL_MESSAGE,
)
from app.schemas.auth_schema import ForgotPasswordSchema

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies
from .guard import guard_login_check, guard_register_failure


def _build_password_reset_context(*, dependencies: Any, email: str) -> Any:
    return dependencies.build_login_attempt_context(
        principal=f"password-reset:{email}",
        remote_addr=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
        forwarded_for=request.headers.get("X-Forwarded-For"),
        real_ip=request.headers.get("X-Real-IP"),
        known_principal=False,
    )


class ForgotPasswordResource(MethodResource):
    @doc(
        description=(
            "Solicita recuperação de senha por link. A resposta é sempre neutra "
            "para evitar enumeração de contas."
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
                    "schema": ForgotPasswordSchema,
                    "example": {"email": "email@email.com"},
                }
            },
        },
        responses={
            200: {"description": "Solicitação recebida com resposta neutra"},
            400: {"description": "Erro de validação"},
            503: {
                "description": "Serviço de autenticação temporariamente indisponível"
            },
            500: {"description": "Erro interno ao solicitar recuperação"},
        },
    )
    @use_kwargs(ForgotPasswordSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        dependencies = get_auth_dependencies()
        email = str(kwargs["email"])
        login_guard = dependencies.get_login_attempt_guard()
        login_context = _build_password_reset_context(
            dependencies=dependencies,
            email=email,
        )
        check_result = guard_login_check(
            login_guard=login_guard,
            login_context=login_context,
        )
        if isinstance(check_result, Response):
            return check_result

        allowed, retry_after = check_result
        if not allowed:
            current_app.logger.info(
                "event=auth.password_reset_rate_limited retry_after_seconds=%s",
                retry_after,
            )
            return compat_success(
                legacy_payload={"message": PASSWORD_RESET_NEUTRAL_MESSAGE},
                status_code=200,
                message=PASSWORD_RESET_NEUTRAL_MESSAGE,
                data={},
            )

        try:
            guard_error = guard_register_failure(
                login_guard=login_guard,
                login_context=login_context,
            )
            if guard_error is not None:
                return guard_error
            result = dependencies.request_password_reset(email)
            return compat_success(
                legacy_payload={"message": result.message},
                status_code=200,
                message=result.message,
                data={},
            )
        except Exception:
            current_app.logger.exception(
                "Password reset request failed due to unexpected error."
            )
            return compat_error(
                legacy_payload={"message": "Password reset request failed"},
                status_code=500,
                message="Password reset request failed",
                error_code="INTERNAL_ERROR",
            )
