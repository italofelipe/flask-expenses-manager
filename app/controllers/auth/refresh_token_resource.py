from __future__ import annotations

from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt, get_jwt_identity, set_refresh_cookies

from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.extensions.database import db
from app.extensions.jwt_revocation_cache import get_jwt_revocation_cache
from app.models.user import User
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class RefreshTokenResource(MethodResource):
    @doc(
        summary="Renovar access token",
        description=(
            "Emite um novo par de tokens (access + refresh) "
            "usando um refresh token válido.\n\n"
            "Rotation:\n"
            "- Cada uso invalida o refresh token anterior (replay attack prevention).\n"
            "- O novo refresh token tem TTL de 7 dias a partir da emissão.\n\n"
            "Fontes aceitas para o refresh token (SEC-GAP-01):\n"
            "- Cookie httpOnly `auraxis_refresh` (recomendado, clientes novos).\n"
            "- Header `Authorization: Bearer <refresh_token>` (legado).\n\n"
            "Headers:\n"
            "- `X-API-Contract`: opcional; `v2` padroniza o envelope."
        ),
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Tokens renovados com sucesso",
                message="Token refreshed",
                data_example={
                    "token": "<access_token>",
                    "refresh_token": "<access_token>",
                },
            ),
            401: json_error_response(
                description="Refresh token inválido, expirado ou já utilizado",
                message="Token invalid or already used",
                error_code="TOKEN_INVALID",
                status_code=401,
            ),
            429: json_error_response(
                description="Muitas requisições de renovação",
                message="Too many requests",
                error_code="RATE_LIMIT_EXCEEDED",
                status_code=429,
            ),
        },
    )
    @jwt_required(refresh=True)
    def post(self) -> Response:
        user_id: str = get_jwt_identity()
        claims = get_jwt()
        incoming_jti: str = claims.get("jti", "")

        user: User | None = db.session.get(User, UUID(user_id))
        if user is None:
            return compat_error(
                legacy_payload={"message": "User not found"},
                status_code=401,
                message="User not found",
                error_code="TOKEN_INVALID",
            )

        # Replay attack guard: the incoming JTI must match the stored refresh JTI.
        if not incoming_jti or user.refresh_token_jti != incoming_jti:
            return compat_error(
                legacy_payload={"message": "Token invalid or already used"},
                status_code=401,
                message="Token invalid or already used",
                error_code="TOKEN_REUSED",
            )

        try:
            dependencies = get_auth_dependencies()
            new_access_token = dependencies.create_access_token(str(user.id))
            new_refresh_token = dependencies.create_refresh_token(str(user.id))
            new_access_jti = dependencies.get_token_jti(new_access_token)
            new_refresh_jti = dependencies.get_token_jti(new_refresh_token)

            user.current_jti = new_access_jti
            user.refresh_token_jti = new_refresh_jti
            db.session.commit()
            get_jwt_revocation_cache().set_current_jti(user_id, new_access_jti)

            response = compat_success(
                legacy_payload={
                    "message": "Token refreshed",
                    "token": new_access_token,
                    "refresh_token": new_refresh_token,
                },
                status_code=200,
                message="Token refreshed",
                data={
                    "token": new_access_token,
                    "refresh_token": new_refresh_token,
                },
            )
            # SEC-GAP-01 — rotate the httpOnly refresh cookie alongside the
            # body payload (dual-mode backward compat during the client
            # migration window).
            set_refresh_cookies(response, new_refresh_token)
            return response
        except Exception:
            current_app.logger.exception(
                "Token refresh failed due to unexpected error."
            )
            return compat_error(
                legacy_payload={"message": "Token refresh failed"},
                status_code=500,
                message="Token refresh failed",
                error_code="INTERNAL_ERROR",
            )
