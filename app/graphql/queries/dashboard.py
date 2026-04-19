from __future__ import annotations

import graphene

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.application.services.transaction_query_service import TransactionQueryService
from app.graphql.auth import get_current_user_required
from app.graphql.dashboard_payloads import (
    build_dashboard_overview_payload,
    build_weekly_summary_payload,
)
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.types import TransactionDashboardPayloadType, WeeklySummaryPayloadType


class DashboardQueryMixin:
    dashboard_overview = graphene.Field(
        TransactionDashboardPayloadType,
        month=graphene.String(required=True),
    )
    weekly_summary = graphene.Field(
        WeeklySummaryPayloadType,
        period=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
    )

    def resolve_dashboard_overview(
        self,
        _info: graphene.ResolveInfo,
        month: str,
    ) -> TransactionDashboardPayloadType:
        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)
        try:
            result = query_service.get_dashboard_overview(month=month)
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc
        return build_dashboard_overview_payload(result)

    def resolve_weekly_summary(
        self,
        _info: graphene.ResolveInfo,
        period: str = "1m",
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> WeeklySummaryPayloadType:
        from datetime import date

        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)

        parsed_start: date | None = None
        parsed_end: date | None = None
        if start_date and end_date:
            try:
                parsed_start = date.fromisoformat(start_date)
                parsed_end = date.fromisoformat(end_date)
            except ValueError as exc:
                raise build_public_graphql_error(
                    "Data inválida. Use o formato YYYY-MM-DD.",
                    code="VALIDATION_ERROR",
                ) from exc

        result = query_service.get_weekly_summary(
            period=period,
            start_date=parsed_start,
            end_date=parsed_end,
        )
        return build_weekly_summary_payload(result)


__all__ = ["DashboardQueryMixin"]
