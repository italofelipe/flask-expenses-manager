from __future__ import annotations

from typing import Any

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.login_identity_service import resolve_login_identity
from app.docs.openapi_helpers import (
    DEPRECATION_HEADER_NAME,
    LEGACY_SUNSET_EXAMPLE,
    SUCCESSOR_FIELD_HEADER_NAME,
    SUNSET_HEADER_NAME,
    WARNING_HEADER_NAME,
    contract_header_param,
    deprecated_headers_doc,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.extensions.database import db
from app.extensions.integration_metrics import increment_metric
from app.http.request_context import get_request_context
from app.schemas.auth_schema import AuthSchema
from app.services.login_attempt_guard_service import (
    LoginAttemptContext,
    LoginAttemptGuardService,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import AuthDependencies, get_auth_dependencies
from .guard import guard_login_check, guard_register_failure, guard_register_success

NAME_LOGIN_DEPRECATION_WARNING = (
    "O campo `name` está em deprecação para login. Use `email`."
)
NAME_LOGIN_SUNSET = LEGACY_SUNSET_EXAMPLE
EMAIL_SUCCESSOR_FIELD = "email"


def _uses_legacy_name_login(*, email: str | None, name: str | None) -> bool:
    return not bool(email) and bool(name)


def _record_login_identifier_metric(
    *, channel: str, uses_legacy_name_login: bool
) -> None:
    identifier = "name_legacy" if uses_legacy_name_login else "email"
    increment_metric(f"auth.login.identifier.{channel}.{identifier}")


def _apply_name_login_deprecation_headers(response: Response) -> Response:
    response.headers[DEPRECATION_HEADER_NAME] = "true"
    response.headers[SUNSET_HEADER_NAME] = NAME_LOGIN_SUNSET
    response.headers[SUCCESSOR_FIELD_HEADER_NAME] = EMAIL_SUCCESSOR_FIELD
    response.headers[WARNING_HEADER_NAME] = NAME_LOGIN_DEPRECATION_WARNING
    return response


def _finalize_login_response(
    response: Response,
    *,
    uses_legacy_name_login: bool,
) -> Response:
    if not uses_legacy_name_login:
        return response
    return _apply_name_login_deprecation_headers(response)


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
            "- `email` é o identificador canônico de login\n"
            "- `name` é aceito apenas como compatibilidade transitória e emite "
            "headers de deprecação\n"
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
                "Credenciais para login. Use `email` como identificador "
                "canônico; `name` permanece em compatibilidade transitória."
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
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
            400: json_error_response(
                description="Credenciais ausentes ou payload inválido",
                message="Missing credentials",
                error_code="VALIDATION_ERROR",
                status_code=400,
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
            401: json_error_response(
                description="Credenciais inválidas",
                message="Invalid credentials",
                error_code="UNAUTHORIZED",
                status_code=401,
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
            429: json_error_response(
                description="Muitas tentativas de login",
                message="Too many login attempts. Try again later.",
                error_code="TOO_MANY_ATTEMPTS",
                status_code=429,
                details_example={"retry_after_seconds": 300},
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
            503: json_error_response(
                description="Serviço de autenticação temporariamente indisponível",
                message="Authentication temporarily unavailable. Try again later.",
                error_code="AUTH_BACKEND_UNAVAILABLE",
                status_code=503,
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
            500: json_error_response(
                description="Erro interno ao efetuar login",
                message="Login failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
                headers=deprecated_headers_doc(
                    successor_field=EMAIL_SUCCESSOR_FIELD,
                    warning=NAME_LOGIN_DEPRECATION_WARNING,
                    sunset=NAME_LOGIN_SUNSET,
                ),
            ),
        },
    )
    @use_kwargs(AuthSchema, location="json")
    def post(self, **kwargs: Any) -> Response:
        email = kwargs.get("email")
        name = kwargs.get("name")
        password = kwargs.get("password")
        uses_legacy_name_login = _uses_legacy_name_login(email=email, name=name)

        if not password or not (email or name):
            return _finalize_login_response(
                compat_error(
                    legacy_payload={"message": "Missing credentials"},
                    status_code=400,
                    message="Missing credentials",
                    error_code="VALIDATION_ERROR",
                ),
                uses_legacy_name_login=uses_legacy_name_login,
            )

        dependencies: AuthDependencies = get_auth_dependencies()
        auth_policy = dependencies.get_auth_security_policy()
        request_context = get_request_context()
        identity = resolve_login_identity(
            email=email,
            name=name,
            find_user_by_email=dependencies.find_user_by_email,
            find_user_by_name=dependencies.find_user_by_name,
        )
        _record_login_identifier_metric(
            channel="rest",
            uses_legacy_name_login=identity.uses_legacy_name_identifier,
        )
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
            return _finalize_login_response(
                check_result,
                uses_legacy_name_login=uses_legacy_name_login,
            )
        allowed, retry_after = check_result

        if not allowed:
            return _finalize_login_response(
                _too_many_attempts_response(retry_after=retry_after),
                uses_legacy_name_login=uses_legacy_name_login,
            )

        password_hash = identity.user.password if identity.user is not None else None
        is_valid_password = dependencies.verify_password(password_hash, str(password))
        if not identity.user or not is_valid_password:
            return _finalize_login_response(
                _invalid_credentials_response(
                    login_guard=login_guard,
                    login_context=login_context,
                ),
                uses_legacy_name_login=uses_legacy_name_login,
            )

        try:
            success_guard_response = guard_register_success(
                login_guard=login_guard,
                login_context=login_context,
            )
            if success_guard_response is not None:
                return _finalize_login_response(
                    success_guard_response,
                    uses_legacy_name_login=uses_legacy_name_login,
                )

            token = dependencies.create_access_token(str(identity.user.id))
            jti = dependencies.get_token_jti(token)
            if identity.user.current_jti != jti:
                identity.user.current_jti = jti
                db.session.commit()
            user_data = {
                "id": str(identity.user.id),
                "name": identity.user.name,
                "email": identity.user.email,
            }
            return _finalize_login_response(
                compat_success(
                    legacy_payload={
                        "message": "Login successful",
                        "token": token,
                        "user": user_data,
                    },
                    status_code=200,
                    message="Login successful",
                    data={"token": token, "user": user_data},
                ),
                uses_legacy_name_login=uses_legacy_name_login,
            )
        except Exception:
            current_app.logger.exception("Login failed due to unexpected error.")
            return _finalize_login_response(
                compat_error(
                    legacy_payload={"message": "Login failed"},
                    status_code=500,
                    message="Login failed",
                    error_code="INTERNAL_ERROR",
                ),
                uses_legacy_name_login=uses_legacy_name_login,
            )
