from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app, request
from flask_apispec.views import MethodResource
from flask_jwt_extended import set_refresh_cookies

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContextService,
)
from app.application.services.email_confirmation_service import (
    EMAIL_CONFIRMATION_INVALID_OR_REUSED_REASON,
    EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
    EMAIL_CONFIRMATION_SUCCESS_MESSAGE,
)
from app.application.services.session_service import create_session
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.extensions.database import db
from app.http.request_context import get_request_context
from app.models.user import User
from app.schemas.auth_schema import ConfirmEmailSchema
from app.services.authenticated_user_payloads import (
    to_authenticated_user_canonical_payload,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .cookie_only_policy import COOKIE_ONLY_HEADER, should_omit_refresh_token_in_body
from .dependencies import AuthDependencies, get_auth_dependencies


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
                data_example={
                    "token": "access-token-issued-after-email-confirmation",
                    "refresh_token": "refresh-token-issued-after-email-confirmation",
                    "session_created": True,
                    "user": {
                        "identity": {
                            "id": "00000000-0000-0000-0000-000000000000",
                            "email": "usuario@auraxis.com.br",
                        },
                        "email_verification": {"verified": True},
                    },
                },
            ),
            400: json_error_response(
                description="Token inválido, expirado ou payload inválido",
                message=EMAIL_CONFIRMATION_INVALID_TOKEN_MESSAGE,
                error_code="VALIDATION_ERROR",
                status_code=400,
                details_example={"reason": "expired"},
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
            dependencies = get_auth_dependencies()
            result = dependencies.confirm_email(str(kwargs["token"]))
            if not result.ok:
                return compat_error(
                    legacy_payload={"message": result.message},
                    status_code=400,
                    message=result.message,
                    error_code="VALIDATION_ERROR",
                    details={
                        "reason": result.reason
                        or EMAIL_CONFIRMATION_INVALID_OR_REUSED_REASON
                    },
                )
            if result.user_id is None:
                current_app.logger.info(
                    "event=auth.email_confirmation_completed "
                    "status=success_without_session"
                )
                return compat_success(
                    legacy_payload={"message": result.message},
                    status_code=200,
                    message=result.message,
                    data={"session_created": False},
                )
            return _build_magic_link_response(
                user_id=result.user_id,
                dependencies=dependencies,
                message=result.message,
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


def _build_magic_link_response(
    *,
    user_id: UUID,
    dependencies: AuthDependencies,
    message: str,
) -> Response:
    """Mint a JWT pair for the verified user and return the canonical envelope.

    The HMAC token already proved possession of the email address, so we treat
    that as sufficient credential to open a session (#1338 magic-link login).
    Mirrors the pattern used by /auth/login.
    """
    user = db.session.get(User, user_id)
    if user is None:
        return compat_error(
            legacy_payload={"message": "Email confirmation failed"},
            status_code=500,
            message="Email confirmation failed",
            error_code="INTERNAL_ERROR",
        )

    access_token = dependencies.create_access_token(str(user.id))
    refresh_token = dependencies.create_refresh_token(str(user.id))
    access_jti = dependencies.get_token_jti(access_token)
    refresh_jti = dependencies.get_token_jti(refresh_token)

    user.current_jti = access_jti
    user.refresh_token_jti = refresh_jti
    request_context = get_request_context()
    create_session(
        user_id=user.id,
        raw_refresh_token=refresh_token,
        refresh_jti=refresh_jti,
        access_jti=access_jti,
        user_agent=request_context.user_agent,
        remote_addr=request_context.client_ip,
    )
    db.session.commit()

    profile = AuthenticatedUserContextService.with_defaults().build_profile(user)
    user_payload = to_authenticated_user_canonical_payload(profile)

    omit_refresh_in_body = should_omit_refresh_token_in_body(
        header_value=request.headers.get(COOKIE_ONLY_HEADER),
    )
    legacy_payload: dict[str, Any] = {
        "message": message,
        "token": access_token,
        "user": user_payload,
    }
    data_payload: dict[str, Any] = {
        "token": access_token,
        "user": user_payload,
        "session_created": True,
    }
    if not omit_refresh_in_body:
        legacy_payload["refresh_token"] = refresh_token
        data_payload["refresh_token"] = refresh_token

    response = compat_success(
        legacy_payload=legacy_payload,
        status_code=200,
        message=message,
        data=data_payload,
    )
    # SEC-GAP-01 — refresh as httpOnly cookie; client can read access_token
    # from response body and the refresh stays inaccessible to JavaScript.
    set_refresh_cookies(response, refresh_token)
    return response
