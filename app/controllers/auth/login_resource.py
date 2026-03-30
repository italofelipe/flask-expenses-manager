from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.login_identity_service import resolve_login_identity
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.extensions.database import db
from app.extensions.integration_metrics import increment_metric
from app.http.request_context import get_request_context
from app.schemas.auth_schema import AuthSchema
from app.services.captcha_service import get_captcha_service
from app.services.login_attempt_guard_service import (
    LoginAttemptContext,
    LoginAttemptGuardService,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import AuthDependencies, get_auth_dependencies
from .guard import guard_login_check, guard_register_failure, guard_register_success


def _record_login_identifier_metric(*, channel: str) -> None:
    increment_metric(f"auth.login.identifier.{channel}.email")


def _invalid_credentials_response(
    *,
    login_guard: LoginAttemptGuardService,
    login_context: LoginAttemptContext,
) -> Response:
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


def _too_many_attempts_response(*, retry_after: int | None) -> Response:
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


class AuthResource(MethodResource):
    @doc(
        summary="Autenticar usuário",
        description=(
            "Autentica o usuário e devolve um token JWT.\n\n"
            "Headers:\n"
            "- `X-API-Contract`: opcional; `v2` padroniza o envelope.\n\n"
            "Payload:\n"
            "- `email` é o identificador obrigatório e canônico de login\n"
            "- `password` é obrigatório\n\n"
            "Sessão:\n"
            "- um login bem-sucedido atualiza o `current_jti` do usuário e "
            "revoga a sessão JWT anterior\n\n"
            "Resposta:\n"
            "- `data.token`: JWT para chamadas autenticadas\n"
            "- `data.user`: dados básicos do usuário autenticado"
        ),
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        requestBody=json_request_body(
            schema=AuthSchema,
            description=(
                "Credenciais para login. `email` é o único identificador "
                "aceito para autenticação."
            ),
            example={
                "email": "italo@auraxis.com.br",
                "password": "MinhaSenha@123",
            },
        ),
        responses={
            200: json_success_response(
                description="Login realizado com sucesso",
                message="Login successful",
                data_example={
                    "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                    "user": {
                        "id": "4b2ef64b-b35d-4ea2-a6f2-4ef3cfb295f1",
                        "name": "Italo Chagas",
                        "email": "italo@auraxis.com.br",
                    },
                },
            ),
            400: json_error_response(
                description="Credenciais ausentes ou payload inválido",
                message="Missing credentials",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Credenciais inválidas",
                message="Invalid credentials",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            429: json_error_response(
                description="Muitas tentativas de login",
                message="Too many login attempts. Try again later.",
                error_code="TOO_MANY_ATTEMPTS",
                status_code=429,
                details_example={"retry_after_seconds": 300},
            ),
            503: json_error_response(
                description="Serviço de autenticação temporariamente indisponível",
                message="Authentication temporarily unavailable. Try again later.",
                error_code="AUTH_BACKEND_UNAVAILABLE",
                status_code=503,
            ),
            500: json_error_response(
                description="Erro interno ao efetuar login",
                message="Login failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @use_kwargs(AuthSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        captcha_token: str | None = kwargs.pop("captcha_token", None)
        if not get_captcha_service().verify(captcha_token):
            return compat_error(
                legacy_payload={"message": "CAPTCHA verification failed"},
                status_code=400,
                message="CAPTCHA verification failed",
                error_code="CAPTCHA_INVALID",
            )

        email = str(kwargs.get("email", ""))
        password = kwargs.get("password")

        if not password or not email:
            return compat_error(
                legacy_payload={"message": "Missing credentials"},
                status_code=400,
                message="Missing credentials",
                error_code="VALIDATION_ERROR",
            )

        dependencies: AuthDependencies = get_auth_dependencies()
        auth_policy = dependencies.get_auth_security_policy()
        request_context = get_request_context()
        identity = resolve_login_identity(
            email=email,
            find_user_by_email=dependencies.find_user_by_email,
        )
        _record_login_identifier_metric(channel="rest")
        login_context = dependencies.build_login_attempt_context(
            principal=identity.principal,
            remote_addr=request_context.client_ip,
            user_agent=request_context.user_agent,
            forwarded_for=request_context.headers.get("x-forwarded-for"),
            real_ip=request_context.headers.get("x-real-ip"),
            known_principal=(
                identity.user is not None
                and auth_policy.login_guard.expose_known_principal
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
            return _too_many_attempts_response(retry_after=retry_after)

        password_hash = identity.user.password if identity.user is not None else None
        is_valid_password = dependencies.verify_password(password_hash, str(password))
        if not identity.user or not is_valid_password:
            return _invalid_credentials_response(
                login_guard=login_guard,
                login_context=login_context,
            )

        try:
            success_guard_response = guard_register_success(
                login_guard=login_guard,
                login_context=login_context,
            )
            if success_guard_response is not None:
                return success_guard_response

            token = dependencies.create_access_token(str(identity.user.id))
            jti = dependencies.get_token_jti(token)
            if identity.user.current_jti != jti:
                identity.user.current_jti = jti
                db.session.commit()
            user_data = {
                "id": str(identity.user.id),
                "name": identity.user.name,
                "email": identity.user.email,
                "email_confirmed": identity.user.email_verified_at is not None,
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
