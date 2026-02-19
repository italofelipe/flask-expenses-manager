# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any

from flask import Response, current_app, request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource

from app.extensions.database import db
from app.schemas.auth_schema import AuthSchema

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies
from .guard import guard_login_check, guard_register_failure, guard_register_success


class AuthResource(MethodResource):
    @doc(
        description="Autenticação de usuário (email ou nome devem ser fornecidos)",
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
                    "schema": AuthSchema,
                    "example": {
                        "email": "email@email.com",
                        "password": "<YOUR_PASSWORD>",
                    },
                }
            },
        },
        responses={
            200: {"description": "Login realizado com sucesso"},
            400: {"description": "Credenciais ausentes"},
            401: {"description": "Credenciais inválidas"},
            503: {
                "description": "Serviço de autenticação temporariamente indisponível"
            },
            500: {"description": "Erro interno ao efetuar login"},
        },
    )
    @use_kwargs(AuthSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        email = kwargs.get("email")
        name = kwargs.get("name")
        password = kwargs.get("password")

        if not password or not (email or name):
            return compat_error(
                legacy_payload={"message": "Missing credentials"},
                status_code=400,
                message="Missing credentials",
                error_code="VALIDATION_ERROR",
            )

        dependencies = get_auth_dependencies()
        auth_policy = dependencies.get_auth_security_policy()
        principal = str(email or name or "")
        user = (
            dependencies.find_user_by_email(str(email))
            if email
            else dependencies.find_user_by_name(str(name))
        )
        login_context = dependencies.build_login_attempt_context(
            principal=principal,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            forwarded_for=request.headers.get("X-Forwarded-For"),
            real_ip=request.headers.get("X-Real-IP"),
            known_principal=(
                user is not None and auth_policy.login_guard.expose_known_principal
            ),
        )
        login_guard = dependencies.get_login_attempt_guard()
        check_result = guard_login_check(
            login_guard=login_guard,
            login_context=login_context,
        )
        if isinstance(check_result, Response):
            return check_result
        allowed, retry_after = check_result

        if not allowed:
            return compat_error(
                legacy_payload={
                    "message": "Too many login attempts. Try again later.",
                    "retry_after_seconds": retry_after,
                },
                status_code=429,
                message="Too many login attempts. Try again later.",
                error_code="TOO_MANY_ATTEMPTS",
                details={"retry_after_seconds": retry_after},
            )

        password_hash = user.password if user is not None else None
        is_valid_password = dependencies.verify_password(password_hash, str(password))
        if not user or not is_valid_password:
            failure_guard_response = guard_register_failure(
                login_guard=login_guard,
                login_context=login_context,
            )
            if failure_guard_response is not None:
                return failure_guard_response
            return compat_error(
                legacy_payload={"message": "Invalid credentials"},
                status_code=401,
                message="Invalid credentials",
                error_code="UNAUTHORIZED",
            )

        try:
            success_guard_response = guard_register_success(
                login_guard=login_guard,
                login_context=login_context,
            )
            if success_guard_response is not None:
                return success_guard_response

            token = dependencies.create_access_token(str(user.id))
            jti = dependencies.get_token_jti(token)
            if user.current_jti != jti:
                user.current_jti = jti
                db.session.commit()
            user_data = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
            }
            return compat_success(
                legacy_payload={
                    "message": "Login successful",
                    "token": token,
                    "user": user_data,
                },
                status_code=200,
                message="Login successful",
                data={"token": token, "user": user_data},
            )
        except Exception:
            current_app.logger.exception("Login failed due to unexpected error.")
            return compat_error(
                legacy_payload={"message": "Login failed"},
                status_code=500,
                message="Login failed",
                error_code="INTERNAL_ERROR",
            )
