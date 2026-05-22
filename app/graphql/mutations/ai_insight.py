"""GraphQL mutation to generate period-aware AI financial insights (MVP-3).

Mirrors `POST /ai/insights/generate`. Each item in the response carries a
`dimension` field (general | transactions | credit_cards | goals | budgets)
so consumers can filter contextually on the UI.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import graphene
from flask import request

from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error
from app.graphql.observability import log_graphql_resolver
from app.services.ai_advisory_service import AIAdvisoryService
from app.services.financial_insight_context_builder import INSIGHT_DIMENSIONS
from app.services.llm_provider import LLMProviderError
from app.utils import timezone_utils

_VALID_PERIOD_TYPES = ("daily", "weekly", "monthly")


class AIInsightItemType(graphene.ObjectType):
    """A single LLM-produced insight item, tagged by dimension."""

    type = graphene.String(required=True)
    dimension = graphene.String(required=True)
    title = graphene.String(required=True)
    message = graphene.String(required=True)
    evidence = graphene.List(graphene.String)


class GenerateAiInsightPayload(graphene.ObjectType):
    ok = graphene.Boolean(required=True)
    period_type = graphene.String()
    period_label = graphene.String()
    period_start = graphene.String()
    period_end = graphene.String()
    summary = graphene.String()
    items = graphene.List(AIInsightItemType)
    context_version = graphene.String()
    cached = graphene.Boolean()
    model = graphene.String()
    tokens_used = graphene.Int()
    cost_usd = graphene.Float()


def _to_item_type(item: dict[str, Any]) -> AIInsightItemType:
    return AIInsightItemType(
        type=item.get("type", ""),
        dimension=item.get("dimension", "general"),
        title=item.get("title", ""),
        message=item.get("message", ""),
        evidence=list(item.get("evidence", []) or []),
    )


class GenerateAiInsightMutation(graphene.Mutation):
    """GraphQL parity for POST /ai/insights/generate.

    Reuses AIAdvisoryService — quota (2x/day Premium), entitlement gate and
    LGPD consent are enforced inside the service. GraphQL surface exposes the
    same payload shape so the frontend hub can render either path identically.
    """

    class Arguments:
        period_type = graphene.String(required=True)
        anchor_date = graphene.String()

    Output = GenerateAiInsightPayload

    @log_graphql_resolver("generateAiInsight")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        period_type: str,
        anchor_date: str | None = None,
    ) -> GenerateAiInsightPayload:
        user = get_current_user_required()

        normalized = (period_type or "").strip().lower()
        if normalized not in _VALID_PERIOD_TYPES:
            raise build_public_graphql_error(
                "period_type must be one of: " + ", ".join(_VALID_PERIOD_TYPES),
                code="VALIDATION_ERROR",
            )

        parsed_anchor: date | None = None
        if anchor_date:
            try:
                parsed_anchor = datetime.strptime(anchor_date, "%Y-%m-%d").date()
            except ValueError as exc:
                raise build_public_graphql_error(
                    "anchor_date must be ISO YYYY-MM-DD",
                    code="VALIDATION_ERROR",
                ) from exc

        service = AIAdvisoryService(user_id=user.id)
        raw_timezone = request.headers.get(timezone_utils.USER_TIMEZONE_HEADER)
        timezone_kwargs: dict[str, Any] = {}
        if raw_timezone not in (None, "") or parsed_anchor is None:
            timezone_resolution = timezone_utils.resolve_user_timezone(raw_timezone)
            timezone_kwargs = {
                "timezone_name": timezone_resolution.name,
                "timezone_fallback": timezone_resolution.fallback_used,
            }
        try:
            result = service.generate_financial_insights(
                period_type=normalized,
                anchor_date=parsed_anchor,
                **timezone_kwargs,
            )
        except LLMProviderError as exc:
            raise build_public_graphql_error(
                "Erro ao gerar insight financeiro",
                code="LLM_PROVIDER_ERROR",
            ) from exc

        items = [_to_item_type(item) for item in result.get("items", [])]
        # All returned items have a dimension; reject malformed (defensive).
        for item in items:
            if item.dimension not in INSIGHT_DIMENSIONS:
                raise build_public_graphql_error(
                    "Insight item with invalid dimension",
                    code="LLM_PROVIDER_ERROR",
                )

        return GenerateAiInsightPayload(
            ok=True,
            period_type=result.get("period_type"),
            period_label=result.get("period_label"),
            period_start=result.get("period_start"),
            period_end=result.get("period_end"),
            summary=result.get("summary"),
            items=items,
            context_version=result.get("context_version"),
            cached=bool(result.get("cached", False)),
            model=result.get("model"),
            tokens_used=int(result.get("tokens_used") or 0),
            cost_usd=float(result.get("cost_usd") or 0),
        )
