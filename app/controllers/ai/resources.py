"""REST resources for LLM-powered AI advisory endpoints (#1206).

Endpoints:
  GET  /ai/insights/spending?month=YYYY-MM  — monthly spending insights
  POST /ai/goals/<goal_id>/projection       — goal projection narrative
  GET  /ai/insights/weekly-summary          — weekly summary narrative

All endpoints require a valid JWT and the "advanced_simulations" entitlement.
"""

from __future__ import annotations

import logging
import uuid
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from flask import Response, request
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.controllers.response_contract import (
    compat_error_response,
    compat_success_response,
)
from app.controllers.transaction.utils import _guard_revoked_token
from app.docs.openapi_helpers import (
    json_error_response,
    json_success_response,
)
from app.middleware.ai_rate_limit import ai_daily_limit
from app.services.ai_advisory_service import AIAdvisoryService
from app.services.analysis_ready_notification_service import (
    dispatch_analysis_ready_notification,
)
from app.services.entitlement_service import has_entitlement
from app.services.llm_provider import LLMProviderError
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

log = logging.getLogger(__name__)

_ENTITLEMENT_KEY = "advanced_simulations"


def _check_entitlement(user_id: UUID) -> Response | None:
    """Return 403 response if user lacks the required entitlement, else None."""
    if not has_entitlement(user_id, _ENTITLEMENT_KEY):
        return compat_error_response(
            legacy_payload={"error": "Recurso exclusivo para assinantes Premium."},
            status_code=403,
            message="Recurso exclusivo para assinantes Premium.",
            error_code="ENTITLEMENT_REQUIRED",
        )
    return None


class AISpendingInsightsResource(MethodResource):
    """GET /ai/insights/spending — monthly spending analysis with AI insights."""

    @doc(
        summary="Insights de gastos com IA (Premium)",
        description=(
            "Analisa os gastos do mês informado e retorna insights gerados por LLM em PT-BR. "  # noqa: E501
            "Requer entitlement 'advanced_simulations' (plano Premium)."
        ),
        tags=["AI Advisory"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "in": "query",
                "type": "string",
                "required": False,
                "description": "Mês no formato YYYY-MM. Padrão: mês atual.",
                "example": "2026-05",
            },
        },
        responses={
            200: json_success_response(
                description="Insights gerados com sucesso",
                message="Insights de gastos gerados com sucesso",
                data_example={
                    "insights": (
                        '[{"type":"saude_financeira","title":"Resumo",'
                        '"message":"Mensagem acionável."}]'
                    ),
                    "items": [
                        {
                            "type": "saude_financeira",
                            "title": "Resumo",
                            "message": "Mensagem acionável.",
                        }
                    ],
                    "tokens_used": 320,
                    "cost_usd": 0.000048,
                    "month": "2026-05",
                    "model": "gpt-4o-mini",
                    "cached": False,
                },
            ),
            401: json_error_response(
                description="Não autenticado",
                message="Token inválido",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            403: json_error_response(
                description="Entitlement insuficiente",
                message="Recurso exclusivo para assinantes Premium.",
                error_code="ENTITLEMENT_REQUIRED",
                status_code=403,
            ),
            500: json_error_response(
                description="Erro interno ou falha do provider LLM",
                message="Erro ao gerar insights de gastos",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    @ai_daily_limit()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = current_user_id()

        entitlement_error = _check_entitlement(user_id)
        if entitlement_error is not None:
            return entitlement_error

        month = request.args.get("month") or None

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = service.generate_spending_insights(month=month)
        except LLMProviderError as exc:
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=500,
                message="Erro ao gerar insights de gastos",
                error_code="INTERNAL_ERROR",
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro interno ao gerar insights"},
                status_code=500,
                message="Erro interno ao gerar insights",
                error_code="INTERNAL_ERROR",
            )

        return compat_success_response(
            legacy_payload=result,
            status_code=200,
            message="Insights de gastos gerados com sucesso",
            data=result,
        )


class AIGoalProjectionResource(MethodResource):
    """POST /ai/goals/<goal_id>/projection — narrative for a goal projection."""

    @doc(
        summary="Narrativa de projeção de meta com IA (Premium)",
        description=(
            "Gera uma narrativa motivacional e prática para uma meta financeira específica, "  # noqa: E501
            "combinando projeção matemática com contexto do usuário. "
            "Requer entitlement 'advanced_simulations' (plano Premium)."
        ),
        tags=["AI Advisory"],
        security=[{"BearerAuth": []}],
        responses={
            200: json_success_response(
                description="Narrativa gerada com sucesso",
                message="Narrativa de projeção gerada com sucesso",
                data_example={
                    "narrative": "Com base no seu plano de aportes...",
                    "tokens_used": 450,
                    "cost_usd": 0.000067,
                    "projection": {"months_to_completion": 24},
                    "model": "gpt-4o-mini",
                },
            ),
            400: json_error_response(
                description="Parâmetros inválidos",
                message="monthly_contribution deve ser um número positivo",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Não autenticado",
                message="Token inválido",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            403: json_error_response(
                description="Entitlement insuficiente",
                message="Recurso exclusivo para assinantes Premium.",
                error_code="ENTITLEMENT_REQUIRED",
                status_code=403,
            ),
            404: json_error_response(
                description="Meta não encontrada",
                message="Meta não encontrada",
                error_code="NOT_FOUND",
                status_code=404,
            ),
            500: json_error_response(
                description="Falha do provider LLM",
                message="Erro ao gerar narrativa de projeção",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    def post(self, goal_id: str) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = current_user_id()

        entitlement_error = _check_entitlement(user_id)
        if entitlement_error is not None:
            return entitlement_error

        # Parse and validate goal_id
        try:
            parsed_goal_id: UUID = uuid.UUID(goal_id)
        except (ValueError, AttributeError):
            return compat_error_response(
                legacy_payload={"error": "goal_id inválido"},
                status_code=400,
                message="goal_id inválido",
                error_code="VALIDATION_ERROR",
            )

        body: dict[str, Any] = request.get_json() or {}
        user_context = str(body.get("user_context", ""))
        raw_contribution = body.get("monthly_contribution")

        if raw_contribution is None:
            return compat_error_response(
                legacy_payload={"error": "monthly_contribution é obrigatório"},
                status_code=400,
                message="monthly_contribution é obrigatório",
                error_code="VALIDATION_ERROR",
            )

        try:
            monthly_contribution = Decimal(str(raw_contribution))
            if monthly_contribution < 0:
                raise ValueError("negative")
        except (InvalidOperation, ValueError):
            return compat_error_response(
                legacy_payload={
                    "error": "monthly_contribution deve ser um número positivo"
                },
                status_code=400,
                message="monthly_contribution deve ser um número positivo",
                error_code="VALIDATION_ERROR",
            )

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = service.generate_goal_projection_narrative(
                goal_id=parsed_goal_id,
                user_context=user_context,
                monthly_contribution=monthly_contribution,
            )
        except ValueError as exc:
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=404,
                message="Meta não encontrada",
                error_code="NOT_FOUND",
            )
        except LLMProviderError as exc:
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=500,
                message="Erro ao gerar narrativa de projeção",
                error_code="INTERNAL_ERROR",
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro interno"},
                status_code=500,
                message="Erro interno ao gerar narrativa",
                error_code="INTERNAL_ERROR",
            )

        return compat_success_response(
            legacy_payload=result,
            status_code=200,
            message="Narrativa de projeção gerada com sucesso",
            data=result,
        )


class AIWeeklySummaryResource(MethodResource):
    """GET /ai/insights/weekly-summary — AI narrative for weekly summary."""

    @doc(
        summary="Briefing semanal com IA (Premium)",
        description=(
            "Gera um briefing narrativo do resumo financeiro da semana atual. "
            "Requer entitlement 'advanced_simulations' (plano Premium)."
        ),
        tags=["AI Advisory"],
        security=[{"BearerAuth": []}],
        responses={
            200: json_success_response(
                description="Briefing gerado com sucesso",
                message="Briefing semanal gerado com sucesso",
                data_example={
                    "narrative": "Esta semana você gastou R$ 1.200...",
                    "tokens_used": 280,
                    "cost_usd": 0.000042,
                    "summary": {"current_week": {}, "previous_week": {}},
                    "model": "gpt-4o-mini",
                },
            ),
            401: json_error_response(
                description="Não autenticado",
                message="Token inválido",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            403: json_error_response(
                description="Entitlement insuficiente",
                message="Recurso exclusivo para assinantes Premium.",
                error_code="ENTITLEMENT_REQUIRED",
                status_code=403,
            ),
            500: json_error_response(
                description="Falha do provider LLM",
                message="Erro ao gerar briefing semanal",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    @ai_daily_limit()
    def get(self) -> Response:
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = current_user_id()

        entitlement_error = _check_entitlement(user_id)
        if entitlement_error is not None:
            return entitlement_error

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = service.generate_weekly_summary_narrative()
        except LLMProviderError as exc:
            return compat_error_response(
                legacy_payload={"error": str(exc)},
                status_code=500,
                message="Erro ao gerar briefing semanal",
                error_code="INTERNAL_ERROR",
            )
        except Exception:
            return compat_error_response(
                legacy_payload={"error": "Erro interno"},
                status_code=500,
                message="Erro interno ao gerar briefing semanal",
                error_code="INTERNAL_ERROR",
            )

        # Notify the user that a new analysis is ready (fire-and-forget).
        # Truncate narrative to 280 chars for the email preview.
        _notify_analysis_ready(
            user_id=user_id, narrative=str(result.get("narrative", ""))
        )

        return compat_success_response(
            legacy_payload=result,
            status_code=200,
            message="Briefing semanal gerado com sucesso",
            data=result,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _notify_analysis_ready(*, user_id: UUID, narrative: str) -> None:
    """Fire-and-forget: send 'analysis ready' notification to the user.

    Swallows all exceptions so notification failures never break the response.
    The notification service itself handles entitlement gating — free users
    are silently skipped without reaching this point in practice because the
    endpoint already requires 'advanced_simulations', but the service enforces
    'email_reminders' independently.
    """
    try:
        preview = (
            narrative[:280].rsplit(" ", 1)[0] if len(narrative) > 280 else narrative
        )
        dispatch_analysis_ready_notification(
            user_id=user_id,
            summary_preview=preview
            or "Sua análise financeira semanal está disponível.",  # noqa: E501
        )
    except Exception as exc:
        log.warning("ai.weekly_summary.notify_failed user_id=%s error=%s", user_id, exc)


class AIInsightHistoryResource(MethodResource):
    """GET /ai/insights/history — paginated AI insight history."""

    @doc(
        summary="Histórico de insights de IA",
        description=(
            "Retorna a lista paginada de insights gerados por IA para o usuário "  # noqa: E501
            "autenticado, ordenada do mais recente para o mais antigo. "
            "Acessível sem entitlement premium."
        ),
        tags=["AI Advisory"],
        security=[{"BearerAuth": []}],
        params={
            "page": {
                "in": "query",
                "type": "integer",
                "required": False,
                "description": "Número da página (base 1). Padrão: 1.",
                "example": 1,
            },
            "per_page": {
                "in": "query",
                "type": "integer",
                "required": False,
                "description": "Itens por página (máx. 50). Padrão: 20.",
                "example": 20,
            },
        },
        responses={
            200: json_success_response(
                description="Lista de insights",
                message="Histórico de insights carregado",
                data_example={
                    "items": [
                        {
                            "id": "uuid",
                            "content": "3 insights...",
                            "insight_type": "daily",
                            "period_label": "2026-05-11",
                            "period_start": "2026-05-11",
                            "period_end": "2026-05-11",
                            "model": "gpt-4o-mini",
                            "tokens_used": 320,
                            "cost_usd": 0.000048,
                            "created_at": "2026-05-11T19:00:00",
                        }
                    ],
                    "page": 1,
                    "per_page": 20,
                    "total": 1,
                },
            ),
            401: json_error_response(
                description="Não autenticado",
                message="Token inválido",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        from app.extensions.database import db
        from app.models.ai_insight import AIInsight

        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = current_user_id()

        try:
            page = max(1, int(request.args.get("page", 1)))
            per_page = min(50, max(1, int(request.args.get("per_page", 20))))
        except (ValueError, TypeError):
            page, per_page = 1, 20

        total = db.session.query(AIInsight).filter_by(user_id=user_id).count()
        rows = (
            db.session.query(AIInsight)
            .filter_by(user_id=user_id)
            .order_by(AIInsight.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        items = [
            {
                "id": str(r.id),
                "content": r.content,
                "insight_type": r.insight_type.value,
                "period_label": r.period_label,
                "period_start": r.period_start.isoformat() if r.period_start else None,
                "period_end": r.period_end.isoformat() if r.period_end else None,
                "model": r.model,
                "tokens_used": r.tokens_used,
                "cost_usd": float(r.cost_usd),
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

        payload = {"items": items, "page": page, "per_page": per_page, "total": total}
        return compat_success_response(
            legacy_payload=payload,
            status_code=200,
            message="Histórico de insights carregado",
            data=payload,
        )


__all__ = [
    "AIGoalProjectionResource",
    "AIInsightHistoryResource",
    "AISpendingInsightsResource",
    "AIWeeklySummaryResource",
]
