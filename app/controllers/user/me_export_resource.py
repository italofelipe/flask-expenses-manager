"""GET /user/me/export — LGPD data portability endpoint (#1256).

Returns the full export package for the authenticated user. The shape is
driven entirely by ``app/application/services/lgpd_export_service.py``
which in turn reads ``app/lgpd/registry.py``.
"""

from __future__ import annotations

from uuid import UUID

from flask import Response
from flask_apispec.views import MethodResource

from app.application.services.lgpd_export_service import build_user_export
from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success

_SUCCESS_MESSAGE = "Pacote LGPD gerado com sucesso."


class MeExportResource(MethodResource):
    """``GET /user/me/export`` — LGPD data portability endpoint."""

    @doc(
        summary="Exportar pacote LGPD do usuário",
        description=(
            "Gera um pacote JSON com todos os dados pessoais do usuário "
            "autenticado, organizados por entidade do registry LGPD. "
            "Inclui metadados de geração e seção ``retentions`` que "
            "explica os dados retidos por obrigação legal (ex: documentos "
            "fiscais com retenção de 5 anos)."
        ),
        tags=["LGPD"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Pacote LGPD gerado",
                message=_SUCCESS_MESSAGE,
                data_example={
                    "metadata": {
                        "generated_at": "2026-05-17T06:00:00+00:00",
                        "user_id": "uuid",
                        "registry_version": "1.0",
                        "scope": "lgpd_full_export",
                    },
                    "users": [{"id": "uuid", "name": "...", "email": "..."}],
                    "consents": [],
                    "transactions": [],
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
            ),
            401: json_error_response(
                description="Token revogado ou ausente",
                message="Token revogado.",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        user_id = UUID(get_active_auth_context().subject)
        package = build_user_export(user_id)
        return compat_success(
            legacy_payload={"message": _SUCCESS_MESSAGE, "data": package},
            status_code=200,
            message=_SUCCESS_MESSAGE,
            data=package,
        )


__all__ = ["MeExportResource"]
