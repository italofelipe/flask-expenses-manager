from __future__ import annotations

from uuid import UUID

import graphene
from graphene import Argument

from app.application.services.transaction_application_service import (
    TransactionApplicationError,
)
from app.application.services.transaction_query_service import TransactionQueryService
from app.graphql.auth import get_current_user_required
from app.graphql.dashboard_payloads import build_dashboard_overview_payload
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.queries.common import paginate
from app.graphql.schema_utils import (
    _parse_optional_date,
    _parse_optional_uuid,
    _resolve_date_range_aliases,
    _resolve_per_page,
    _validate_pagination_values,
)
from app.graphql.types import (
    TransactionDashboardPayloadType,
    TransactionDueCountsType,
    TransactionDueRangePayloadType,
    TransactionListPayloadType,
    TransactionSummaryPayloadType,
    TransactionTypeObject,
)


class TransactionQueryMixin:
    transactions = graphene.Field(
        TransactionListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        type=graphene.String(),
        status=graphene.String(),
        start_date=graphene.String(),
        end_date=graphene.String(),
        tag_id=graphene.UUID(),
        account_id=graphene.UUID(),
        credit_card_id=graphene.UUID(),
    )
    transaction_summary = graphene.Field(
        TransactionSummaryPayloadType,
        month=graphene.String(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        page_size=Argument(
            graphene.Int,
            deprecation_reason="Use perPage.",
        ),
    )
    transaction_dashboard = graphene.Field(
        TransactionDashboardPayloadType,
        month=graphene.String(required=True),
        deprecation_reason="Use dashboardOverview.",
    )
    transaction_due_range = graphene.Field(
        TransactionDueRangePayloadType,
        start_date=graphene.String(),
        end_date=graphene.String(),
        initial_date=Argument(
            graphene.String,
            deprecation_reason="Use startDate.",
        ),
        final_date=Argument(
            graphene.String,
            deprecation_reason="Use endDate.",
        ),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
        order_by=graphene.String(default_value="overdue_first"),
    )
    transaction = graphene.Field(
        TransactionTypeObject,
        transaction_id=graphene.UUID(required=True),
    )

    def resolve_transactions(
        self,
        _info: graphene.ResolveInfo,
        page: int,
        per_page: int,
        type: str | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        tag_id: UUID | None = None,
        account_id: UUID | None = None,
        credit_card_id: UUID | None = None,
    ) -> TransactionListPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)
        result = query_service.get_active_transactions(
            page=page,
            per_page=per_page,
            transaction_type=type,
            status=status,
            start_date=_parse_optional_date(start_date, "start_date"),
            end_date=_parse_optional_date(end_date, "end_date"),
            tag_id=_parse_optional_uuid(tag_id, "tag_id"),
            account_id=_parse_optional_uuid(account_id, "account_id"),
            credit_card_id=_parse_optional_uuid(credit_card_id, "credit_card_id"),
        )
        pagination = result["pagination"]
        return TransactionListPayloadType(
            items=[
                TransactionTypeObject(**item)
                for item in result["items"]
                if isinstance(item, dict)
            ],
            pagination=paginate(
                total=int(pagination["total"]),
                page=int(pagination["page"]),
                per_page=int(pagination["per_page"]),
            ),
        )

    def resolve_transaction(
        self,
        _info: graphene.ResolveInfo,
        transaction_id: graphene.UUID,
    ) -> TransactionTypeObject:
        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)
        try:
            item = query_service.get_transaction(transaction_id)
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc
        return TransactionTypeObject(**item)

    def resolve_transaction_summary(
        self,
        _info: graphene.ResolveInfo,
        month: str,
        page: int,
        per_page: int = 10,
        page_size: int | None = None,
    ) -> TransactionSummaryPayloadType:
        effective_per_page = _resolve_per_page(
            per_page=per_page,
            legacy_page_size=page_size,
        )
        _validate_pagination_values(page, effective_per_page)
        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)
        try:
            result = query_service.get_month_summary(
                month=month,
                page=page,
                per_page=effective_per_page,
            )
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc

        paginated = result["paginated"]
        return TransactionSummaryPayloadType(
            month=str(result["month"]),
            income_total=float(result["income_total"]),
            expense_total=float(result["expense_total"]),
            items=[
                TransactionTypeObject(**item)
                for item in paginated["data"]
                if isinstance(item, dict)
            ],
            pagination=paginate(
                total=int(paginated["total"]),
                page=int(paginated["page"]),
                per_page=int(paginated["page_size"]),
            ),
        )

    def resolve_transaction_dashboard(
        self, _info: graphene.ResolveInfo, month: str
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

    def resolve_transaction_due_range(
        self,
        _info: graphene.ResolveInfo,
        start_date: str | None = None,
        end_date: str | None = None,
        initial_date: str | None = None,
        final_date: str | None = None,
        page: int = 1,
        per_page: int = 10,
        order_by: str = "overdue_first",
    ) -> TransactionDueRangePayloadType:
        _validate_pagination_values(page, per_page)
        effective_start_date, effective_end_date = _resolve_date_range_aliases(
            start_date=start_date,
            end_date=end_date,
            legacy_initial_date=initial_date,
            legacy_final_date=final_date,
        )
        user = get_current_user_required()
        query_service = TransactionQueryService.with_defaults(user.id)
        try:
            result = query_service.get_due_transactions(
                start_date=effective_start_date,
                end_date=effective_end_date,
                page=page,
                per_page=per_page,
                order_by=order_by,
            )
        except TransactionApplicationError as exc:
            raise build_public_graphql_error(
                exc.message,
                code=to_public_graphql_code(exc.code),
            ) from exc

        counts = result["counts"]
        pagination = result["pagination"]
        return TransactionDueRangePayloadType(
            items=[
                TransactionTypeObject(**item)
                for item in result["items"]
                if isinstance(item, dict)
            ],
            counts=TransactionDueCountsType(
                total_transactions=int(counts["total_transactions"]),
                income_transactions=int(counts["income_transactions"]),
                expense_transactions=int(counts["expense_transactions"]),
            ),
            pagination=paginate(
                total=int(pagination["total"]),
                page=int(pagination["page"]),
                per_page=int(pagination["per_page"]),
            ),
        )
