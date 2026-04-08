from __future__ import annotations

import secrets
from typing import Any
from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource
from werkzeug.security import generate_password_hash

from app.application.services.password_verification_service import (
    verify_password_with_timing_protection,
)
from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.extensions.database import db
from app.models.user import User
from app.schemas.user_schemas import DeleteAccountSchema
from app.services.email_provider import EmailMessage, get_default_email_provider
from app.services.email_templates import render_account_deletion_email
from app.utils.datetime_utils import utc_now_naive
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import get_user_dependencies


def _anonymise_user(user: User) -> None:
    """Anonymise all PII fields in-place (LGPD erasure)."""
    user.name = "Deleted User"
    user.email = f"deleted_{user.id}@deleted.auraxis"
    # Generate a random bcrypt hash so the account can never be re-used.
    user.password = generate_password_hash(secrets.token_urlsafe(32))
    user.birth_date = None
    user.state_uf = None
    user.occupation = None
    user.gender = None
    user.financial_objectives = None
    user.monthly_income_net = 0
    user.monthly_expenses = 0
    user.net_worth = 0
    user.initial_investment = 0
    user.monthly_investment = 0
    user.investment_goal_date = None
    # Revoke JWT session.
    user.current_jti = None
    user.refresh_token_jti = None
    # Mark soft-delete timestamp.
    user.deleted_at = utc_now_naive()


class DeleteMeResource(MethodResource):
    @doc(
        summary="Excluir conta do usuário (LGPD)",
        description=(
            "Anonimiza permanentemente todos os dados pessoais do usuário autenticado "
            "(soft-delete LGPD). Requer confirmação de senha.\n\n"
            "Após a exclusão:\n"
            "- Todos os campos de PII são anonimizados\n"
            "- O JWT é revogado (sessão encerrada)\n"
            "- O usuário não consegue mais fazer login\n\n"
            "Esta ação é irreversível."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        requestBody=json_request_body(
            schema=DeleteAccountSchema,
            description="Senha atual do usuário para confirmar a exclusão.",
            example={"password": "MinhaSenha@123"},
        ),
        responses={
            200: json_success_response(
                description="Conta excluída com sucesso",
                message="Account deleted.",
                data_example={},
            ),
            401: json_error_response(
                description="Token inválido ou expirado",
                message="Token revogado",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            403: json_error_response(
                description="Senha incorreta",
                message="Invalid credentials.",
                error_code="INVALID_CREDENTIALS",
                status_code=403,
            ),
            422: json_error_response(
                description="Campo 'password' ausente ou inválido",
                message="Validation error",
                error_code="VALIDATION_ERROR",
                status_code=422,
            ),
        },
    )
    @jwt_required()
    @use_kwargs(DeleteAccountSchema(), location="json")
    def delete(self, **kwargs: Any) -> Response:
        auth_context = get_active_auth_context()
        dependencies = get_user_dependencies()
        user: User | None = dependencies.get_user_by_id(UUID(auth_context.subject))

        if not user or user.deleted_at is not None:
            return compat_error(
                legacy_payload={"message": "Token revogado ou usuário não encontrado"},
                status_code=401,
                message="Token revogado ou usuário não encontrado",
                error_code="UNAUTHORIZED",
            )

        if (
            auth_context.jti is None
            or not hasattr(user, "current_jti")
            or user.current_jti != auth_context.jti
        ):
            return compat_error(
                legacy_payload={"message": "Token revogado"},
                status_code=401,
                message="Token revogado",
                error_code="UNAUTHORIZED",
            )

        plain_password: str = str(kwargs.get("password", ""))
        password_valid = verify_password_with_timing_protection(
            password_hash=user.password,
            plain_password=plain_password,
        )
        if not password_valid:
            return compat_error(
                legacy_payload={"message": "Invalid credentials."},
                status_code=403,
                message="Invalid credentials.",
                error_code="INVALID_CREDENTIALS",
            )

        # Capture the real email address before PII erasure.
        original_email = user.email

        _anonymise_user(user)
        db.session.commit()

        # Send deletion confirmation — best-effort; never block the response.
        try:
            html, text = render_account_deletion_email()
            get_default_email_provider().send(
                EmailMessage(
                    to_email=original_email,
                    subject="Sua conta Auraxis foi excluída",
                    html=html,
                    text=text,
                    tag="account_deletion",
                )
            )
        except Exception:
            current_app.logger.exception(
                "account_deletion: failed to dispatch confirmation email to %s",
                original_email,
            )

        return compat_success(
            legacy_payload={"message": "Account deleted.", "success": True},
            status_code=200,
            message="Account deleted.",
            data={"success": True},
        )
