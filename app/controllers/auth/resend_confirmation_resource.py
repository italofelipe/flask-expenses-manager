from __future__ import annotations

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.email_confirmation_service import (
    EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
)
from app.auth import current_user_id
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_error, compat_success
from .dependencies import get_auth_dependencies


class ResendConfirmationResource(MethodResource):
    @doc(
        summary="Reenviar confirmacao de conta",
        description=(
            "Reenvia o email de confirmacao do usuario autenticado. "
            "Requer token JWT valido no header Authorization. "
            "A resposta e neutra para evitar enumeracao de contas."
        ),
        tags=["Autenticação"],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Solicitação recebida com resposta neutra",
                message=EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
                data_example={},
            ),
            401: json_error_response(
                description="Token JWT ausente ou inválido",
                message="Missing or invalid authorization token",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            500: json_error_response(
                description="Erro interno ao reenviar confirmacao",
                message="Email confirmation resend failed",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    def post(self) -> Response:
        try:
            uid = current_user_id()
            dependencies = get_auth_dependencies()
            user = dependencies.get_user_by_id(uid)
            if user is None:
                return compat_success(
                    legacy_payload={"message": EMAIL_CONFIRMATION_NEUTRAL_MESSAGE},
                    status_code=200,
                    message=EMAIL_CONFIRMATION_NEUTRAL_MESSAGE,
                    data={},
                )
            result = dependencies.resend_email_confirmation(user.email)
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
