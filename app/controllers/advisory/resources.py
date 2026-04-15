from __future__ import annotations

from flask import Response
from flask_apispec.views import MethodResource

from app.application.services.advisory_service import (
    AdvisoryRateLimitError,
    AdvisoryService,
)
from app.auth import current_user_id
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)
from app.controllers.transaction.utils import _guard_revoked_token
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required


class AdvisoryInsightsResource(MethodResource):
    @doc(
        summary="Gerar insights financeiros personalizados (AI advisory)",
        description=(
            "Analisa os dados financeiros do usuário e retorna insights "
            "personalizados gerados por LLM. "
            "Insights são cacheados por 24 h. "
            "Limite: 5 chamadas por dia por usuário."
        ),
        tags=["Advisory"],
        security=[{"BearerAuth": []}],
        params={
            **contract_header_param(supported_version="v2"),
        },
        responses={
            200: json_success_response(
                description="Insights gerados com sucesso",
                message="Insights financeiros gerados com sucesso",
                data_example={
                    "insights": [
                        {
                            "type": "gasto_elevado",
                            "title": "Gastos acima da média",
                            "message": "Gastos variáveis acima de 30% da renda.",
                        }
                    ],
                    "generated_at": "2026-04-15",
                    "source": "llm",
                    "calls_remaining_today": 4,
                },
            ),
            401: json_error_response(
                description="Não autenticado",
                message="Token inválido",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            429: json_error_response(
                description="Rate limit atingido",
                message="Limite diário de advisory atingido.",
                error_code="RATE_LIMIT_EXCEEDED",
                status_code=429,
            ),
            500: json_error_response(
                description="Erro interno",
                message="Erro ao gerar insights",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_uuid = current_user_id()
        service = AdvisoryService(user_id=user_uuid)

        try:
            result = service.get_insights()
        except AdvisoryRateLimitError as exc:
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=429,
                message=str(exc),
                error_code="RATE_LIMIT_EXCEEDED",
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro ao gerar insights de advisory"},
                status_code=500,
                message="Erro ao gerar insights de advisory",
                error_code="INTERNAL_ERROR",
            )

        payload = dict(result)
        return compat_success_response(
            legacy_payload=payload,
            status_code=200,
            message="Insights financeiros gerados com sucesso",
            data=payload,
        )


__all__ = ["AdvisoryInsightsResource"]
