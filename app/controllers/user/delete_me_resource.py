from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.lgpd_deletion_service import delete_user_account
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
from app.http.request_context import current_request_id
from app.models.audit_event import AuditEvent
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


def _persist_deletion_audit(
    user_id: UUID,
    action: str,
    *,
    extra: str | None = None,
    persist_user_link: bool = True,
) -> None:
    """Persist an LGPD account-deletion audit event.

    Pre-deletion events (``persist_user_link=True``) carry the original
    ``user_id`` so the trail proves *who* requested erasure. The
    registry-driven anonymisation pass then nulls that column for any
    pre-existing audit rows, including the one we just wrote.

    Post-deletion events (``persist_user_link=False``) are persisted
    *after* the anonymisation pass, so they would otherwise leak the
    deleted user's id back into ``audit_events``. We write ``user_id``
    as ``NULL`` directly and keep the link only in ``entity_id`` (which
    is a free-form domain identifier, not a PII column).

    Best-effort by design: a failure here must never cascade into a 500
    on the deletion request itself.
    """
    try:
        event = AuditEvent(
            request_id=current_request_id(default=""),
            method="SYSTEM",
            path="/user/me",
            status=0,
            user_id=str(user_id) if persist_user_link else None,
            entity_type="user",
            entity_id=str(user_id),
            action=action,
            actor_id=str(user_id) if persist_user_link else None,
            extra=extra,
        )
        db.session.add(event)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "lgpd_audit_event_failed action=%s user_id=%s",
            action,
            user_id,
        )


def _send_deletion_email(original_email: str) -> None:
    """Dispatch the account-deleted confirmation email (best-effort)."""
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


class DeleteMeResource(MethodResource):
    @doc(
        summary="Excluir conta do usuário (LGPD)",
        description=(
            "Apaga ou anonimiza permanentemente os dados pessoais do usuário "
            "autenticado, executando a estratégia de deleção registrada no "
            "registry LGPD para cada entidade. Requer confirmação de senha.\n\n"
            "Após a exclusão:\n"
            "- Entidades com `DELETE` são removidas do banco (transactions, "
            "goals, accounts, etc.)\n"
            "- Entidades com `ANONYMIZE` mantêm a linha com PII anonimizado "
            "(User, audit_events, subscriptions, etc.)\n"
            "- Entidades com `RETAIN` são preservadas por obrigação fiscal "
            "(fiscal_documents, etc.)\n"
            "- O JWT é revogado (sessão encerrada)\n"
            "- Refresh tokens e push subscriptions são removidos\n"
            "- O usuário não consegue mais fazer login\n\n"
            "A resposta inclui o relatório de auditoria com a contagem por "
            "entidade e a metadata de retenções legais. Esta ação é irreversível."
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
                data_example={
                    "success": True,
                    "report": {
                        "user_id": "uuid",
                        "deleted_at": "2026-05-17T06:00:00",
                        "summary": {
                            "deleted": {"transactions": 47, "goals": 3},
                            "anonymized": {"users": 1, "audit_events": 12},
                            "retained": {"fiscal_documents": 5},
                        },
                        "retentions": [
                            {
                                "entity": "fiscal_documents",
                                "reason": "fiscal",
                                "retention_days": 1825,
                                "explanation": (
                                    "Fiscal documents (NF, receipts) — "
                                    "Brazilian tax retention"
                                ),
                            }
                        ],
                    },
                },
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

        # Capture identifying values before the deletion blanks them out.
        original_email = user.email
        user_id = user.id
        started_at = utc_now_naive().isoformat()

        # 1) Persist the "started" trail BEFORE any data is touched. If the
        #    deletion crashes mid-flight this row survives as evidence the
        #    request was authenticated and authorised.
        _persist_deletion_audit(
            user_id,
            action="lgpd_account_deletion_started",
            extra=f'{{"started_at": "{started_at}"}}',
            persist_user_link=True,
        )

        # 2) Run the registry-driven deletion. The service commits its own
        #    transaction so failures here are atomic.
        try:
            report = delete_user_account(user_id)
        except Exception:
            db.session.rollback()
            current_app.logger.exception(
                "lgpd_account_deletion_failed user_id=%s", user_id
            )
            return compat_error(
                legacy_payload={"message": "Account deletion failed."},
                status_code=500,
                message="Account deletion failed.",
                error_code="DELETE_FAILED",
            )

        # 3) Persist the "completed" trail. The previously anonymised
        #    ``user_id`` column on AuditEvent is the registry strategy —
        #    we still record it here so the *count* of LGPD events is
        #    accurate. The deletion pass already ran, so this row's
        #    ``user_id`` is written *after* anonymisation and survives.
        completed_at = utc_now_naive().isoformat()
        summary = report.get("summary", {})
        deleted_n = sum((summary.get("deleted") or {}).values())
        anon_n = sum((summary.get("anonymized") or {}).values())
        retained_n = sum((summary.get("retained") or {}).values())
        _persist_deletion_audit(
            user_id,
            action="lgpd_account_deletion_completed",
            extra=(
                f'{{"completed_at": "{completed_at}",'
                f' "deleted_rows": {deleted_n},'
                f' "anonymised_rows": {anon_n},'
                f' "retained_rows": {retained_n}}}'
            ),
            persist_user_link=False,
        )

        # 4) Best-effort confirmation email.
        _send_deletion_email(original_email)

        return compat_success(
            legacy_payload={
                "message": "Account deleted.",
                "success": True,
                "report": report,
            },
            status_code=200,
            message="Account deleted.",
            data={"success": True, "report": report},
        )
