"""REST resources for the LGPD versioned consents endpoints (#1259).

Endpoints:

- ``GET /me/consents`` — list the latest event per kind for the user.
- ``POST /me/consents`` — record a grant or revocation event (idempotent).
- ``DELETE /me/consents/<kind>`` — convenience revocation shortcut.

All endpoints require an authenticated JWT and operate exclusively on
the caller's own user_id.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.consent_service import (
    list_consents_for_user,
    record_consent,
)
from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.http.request_context import current_request_id
from app.models.consent import (
    Consent,
    ConsentAction,
    ConsentKind,
    ConsentSource,
)
from app.schemas.consent_schemas import ConsentRecordSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import consent_error, consent_success


def _serialize(event: Consent) -> dict[str, Any]:
    """Serialise a Consent row into the public response shape."""
    return {
        "id": str(event.id),
        "kind": event.kind.value,
        "version": event.version,
        "action": event.action.value,
        "source": event.source.value,
        "created_at": event.created_at.isoformat(),
    }


class ConsentCollectionResource(MethodResource):
    """``GET`` and ``POST`` on ``/me/consents``."""

    @doc(
        summary="Listar consentimentos LGPD do usuário",
        description=(
            "Retorna o evento mais recente para cada tipo de consentimento "
            "que o usuário já registrou. Tipos nunca registrados não "
            "aparecem na lista."
        ),
        tags=["LGPD"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Lista de consentimentos atual",
                message="Consentimentos listados com sucesso.",
                data_example={
                    "items": [
                        {
                            "id": "uuid",
                            "kind": "terms",
                            "version": "1.0",
                            "action": "granted",
                            "source": "web",
                            "created_at": "2026-05-17T12:00:00",
                        }
                    ],
                    "total": 1,
                },
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        user_id = UUID(get_active_auth_context().subject)
        events = list_consents_for_user(user_id)
        items = [_serialize(e) for e in events]
        return consent_success(
            message="Consentimentos listados com sucesso.",
            data={"items": items, "total": len(items)},
        )

    @doc(
        summary="Registrar consentimento LGPD",
        description=(
            "Registra um evento de aceite ou revogação de um tipo de "
            "consentimento em uma versão específica. Idempotente sobre "
            "(kind, version, action) — replay do mesmo evento retorna a "
            "linha original."
        ),
        tags=["LGPD"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            201: json_success_response(
                description="Consentimento registrado",
                message="Consentimento registrado com sucesso.",
                data_example={
                    "id": "uuid",
                    "kind": "terms",
                    "version": "1.0",
                    "action": "granted",
                    "source": "web",
                    "created_at": "2026-05-17T12:00:00",
                },
            ),
            400: json_error_response(
                description="Dados inválidos",
                message="kind/action/source inválido.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    @use_kwargs(ConsentRecordSchema(), location="json")
    def post(self, **kwargs: object) -> Response:
        user_id = UUID(get_active_auth_context().subject)
        kind = ConsentKind(kwargs["kind"])
        action = ConsentAction(kwargs["action"])
        source = ConsentSource(kwargs["source"])
        version = str(kwargs["version"])

        event = record_consent(
            user_id=user_id,
            kind=kind,
            version=version,
            action=action,
            source=source,
        )

        current_app.logger.info(
            "event=consent.recorded user_id=%s kind=%s version=%s action=%s "
            "source=%s request_id=%s",
            user_id,
            kind.value,
            version,
            action.value,
            source.value,
            current_request_id(),
        )
        return consent_success(
            message="Consentimento registrado com sucesso.",
            data=_serialize(event),
            status_code=201,
        )


class ConsentRevokeResource(MethodResource):
    """``DELETE /me/consents/<kind>`` — convenience revoke shortcut."""

    @doc(
        summary="Revogar consentimento LGPD",
        description=(
            "Atalho para registrar um evento de revogação. Versão "
            "revogada é a última versão aceita do mesmo tipo, ou '1.0' "
            "se nunca houve evento anterior."
        ),
        tags=["LGPD"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            204: {"description": "Consentimento revogado"},
            400: json_error_response(
                description="Kind inválido",
                message="Kind não suportado.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    def delete(self, kind: str) -> Response:
        try:
            kind_enum = ConsentKind(kind)
        except ValueError:
            return consent_error(
                message="Kind não suportado.",
                status_code=400,
                error_code="VALIDATION_ERROR",
            )

        user_id = UUID(get_active_auth_context().subject)
        version = _latest_version_for(user_id, kind_enum)

        record_consent(
            user_id=user_id,
            kind=kind_enum,
            version=version,
            action=ConsentAction.REVOKED,
            source=ConsentSource.API,
        )

        current_app.logger.info(
            "event=consent.revoked user_id=%s kind=%s version=%s request_id=%s",
            user_id,
            kind_enum.value,
            version,
            current_request_id(),
        )
        return Response(status=204)


def _latest_version_for(user_id: UUID, kind: ConsentKind) -> str:
    """Return the most recent version seen for ``(user, kind)``.

    Falls back to ``"1.0"`` when the user has never registered a
    consent event for this kind — covers the case where a client
    revokes a default-on consent without ever having explicitly
    accepted it.
    """
    latest: Consent | None = (
        Consent.query.filter_by(user_id=user_id, kind=kind)
        .order_by(Consent.created_at.desc())
        .first()
    )
    if latest is not None:
        return str(latest.version)
    return "1.0"
