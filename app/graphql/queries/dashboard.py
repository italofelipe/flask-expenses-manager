from __future__ import annotations

import graphene

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.application.services.transaction_query_service import TransactionQueryService
from app.graphql.auth import get_current_user_required
from app.graphql.dashboard_payloads import build_dashboard_overview_payload
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.types import TransactionDashboardPayloadType


class DashboardQueryMixin:
    dashboard_overview = graphene.Field(
        TransactionDashboardPayloadType,
        month=graphene.String(required=True),
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


__all__ = ["DashboardQueryMixin"]
