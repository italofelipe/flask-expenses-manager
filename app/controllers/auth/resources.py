# mypy: disable-error-code=misc

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID

from flask import Response, abort, current_app, jsonify, make_response, request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    create_access_token,
    get_jti,
    get_jwt_identity,
    jwt_required,
)
from webargs import ValidationError as WebargsValidationError
from webargs.flaskparser import parser
from werkzeug.security import generate_password_hash

from app.application.services.auth_security_policy_service import (
    get_auth_security_policy,
)
from app.application.services.password_verification_service import (
    verify_password_with_timing_protection,
)
from app.extensions.database import db
from app.models.user import User
from app.schemas.auth_schema import AuthSchema
from app.schemas.user_schemas import UserRegistrationSchema
from app.services.login_attempt_guard_service import (
    build_login_attempt_context,
    get_login_attempt_guard,
)
from app.utils.response_builder import error_payload

from .blueprint import auth_bp
from .contracts import (
    compat_error,
    compat_success,
    is_v2_contract,
    registration_ack_payload,
)
from .guard import guard_login_check, guard_register_failure, guard_register_success


class RegisterResource(MethodResource):
    @doc(
        description="Cria um novo usuário no sistema",
        tags=["Autenticação"],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            201: {"description": "Usuário criado com sucesso"},
            400: {"description": "Erro de validação"},
            409: {"description": "Email já registrado"},
            500: {"description": "Erro interno do servidor"},
        },
    )
    @use_kwargs(UserRegistrationSchema, location="json")
    def post(self, **validated_data: Any) -> Response:
        auth_policy = get_auth_security_policy()
        duplicate_user = User.query.filter_by(email=validated_data["email"]).first()
        if duplicate_user:
            if auth_policy.registration.conceal_conflict:
                return compat_success(
                    legacy_payload=registration_ack_payload(
                        auth_policy.registration.accepted_message
                    ),
                    status_code=201,
                    message=auth_policy.registration.accepted_message,
                    data={},
                )
            return compat_error(
                legacy_payload={
                    "message": auth_policy.registration.conflict_message,
                    "data": None,
                },
                status_code=409,
                message=auth_policy.registration.conflict_message,
                error_code="CONFLICT",
            )

        try:
            hashed_password = generate_password_hash(validated_data["password"])
            user = User(
                name=validated_data["name"],
                email=validated_data["email"],
                password=hashed_password,
            )
            db.session.add(user)
            db.session.flush()
            db.session.commit()

            if auth_policy.registration.conceal_conflict:
                return compat_success(
                    legacy_payload=registration_ack_payload(
                        auth_policy.registration.accepted_message
                    ),
                    status_code=201,
                    message=auth_policy.registration.accepted_message,
                    data={},
                )

            user_data = {
                "id": str(user.id),
                "name": user.name,
                "email": user.email,
            }
            return compat_success(
                legacy_payload={
                    "message": auth_policy.registration.created_message,
                    "data": user_data,
                },
                status_code=201,
                message=auth_policy.registration.created_message,
                data={"user": user_data},
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Failed to create user.")
            return compat_error(
                legacy_payload={"message": "Failed to create user"},
                status_code=500,
                message="Failed to create user",
                error_code="INTERNAL_ERROR",
            )


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

        principal = str(email or name or "")
        user = (
            User.query.filter_by(email=email).first()
            if email
            else User.query.filter_by(name=name).first()
        )
        login_context = build_login_attempt_context(
            principal=principal,
            remote_addr=request.remote_addr,
            user_agent=request.headers.get("User-Agent"),
            forwarded_for=request.headers.get("X-Forwarded-For"),
            real_ip=request.headers.get("X-Real-IP"),
            known_principal=(
                user is not None
                and get_auth_security_policy().login_guard.expose_known_principal
            ),
        )
        login_guard = get_login_attempt_guard()
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
        is_valid_password = verify_password_with_timing_protection(
            password_hash=password_hash,
            plain_password=password,
        )
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
            token = create_access_token(
                identity=str(user.id), expires_delta=timedelta(hours=1)
            )
            jti = get_jti(token)
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


class LogoutResource(MethodResource):
    @doc(
        description="Revoga o token JWT atual (logout do usuário)",
        tags=["Autenticação"],
        security=[{"BearerAuth": []}],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            200: {"description": "Logout realizado com sucesso"},
        },
    )
    @jwt_required()
    def post(self) -> Response:
        identity = get_jwt_identity()
        user = db.session.get(User, UUID(str(identity)))
        if user:
            user.current_jti = None
            db.session.commit()
        return compat_success(
            legacy_payload={"message": "Logout successful"},
            status_code=200,
            message="Logout successful",
            data={},
        )


auth_bp.add_url_rule(
    "/register", view_func=RegisterResource.as_view("registerresource")
)
auth_bp.add_url_rule("/login", view_func=AuthResource.as_view("authresource"))
auth_bp.add_url_rule("/logout", view_func=LogoutResource.as_view("logoutresource"))


@parser.error_handler
def handle_webargs_error(
    err: WebargsValidationError,
    req: Any,
    schema: Any = None,
    *,
    error_status_code: Any = None,
    error_headers: Any = None,
    **kwargs: Any,
) -> Any:
    """
    Converte erros de validação (422) do Webargs/Marshmallow em uma
    resposta JSON 400 mais amigável para o cliente.
    """
    error_message = "Validation error"
    if "password" in err.messages:
        error_message = (
            "Senha inválida: não atende aos critérios mínimos de segurança "
            "(mín. 10 caracteres, 1 letra maiúscula, 1 número e 1 símbolo)."
        )

    payload: dict[str, Any] = {
        "message": error_message,
        "errors": err.messages,
    }
    if is_v2_contract():
        payload = error_payload(
            message=error_message,
            code="VALIDATION_ERROR",
            details={"errors": err.messages},
        )

    resp = make_response(jsonify(payload), 400)
    abort(resp)
    raise AssertionError
