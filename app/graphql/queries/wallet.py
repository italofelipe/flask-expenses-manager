from __future__ import annotations

from uuid import UUID

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.queries.common import paginate
from app.graphql.schema_utils import (
    _get_owned_wallet_or_error,
    _validate_pagination_values,
    _wallet_to_graphql_payload,
)
from app.graphql.types import (
    PaginationType,
    TickerType,
    WalletHistoryItemType,
    WalletHistoryPayloadType,
    WalletListPayloadType,
    WalletType,
)
from app.models.user_ticker import UserTicker
from app.models.wallet import Wallet


class WalletQueryMixin:
    wallet_entries = graphene.Field(
        WalletListPayloadType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=10),
    )
    wallet_history = graphene.Field(
        WalletHistoryPayloadType,
        investment_id=graphene.UUID(required=True),
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=5),
    )
    tickers = graphene.List(TickerType)

    def resolve_wallet_entries(
        self, info: graphene.ResolveInfo, page: int, per_page: int
    ) -> WalletListPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        pagination = (
            Wallet.query.filter_by(user_id=user.id)
            .order_by(Wallet.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        items = [
            WalletType(**_wallet_to_graphql_payload(item)) for item in pagination.items
        ]
        return WalletListPayloadType(
            items=items,
            pagination=paginate(
                total=pagination.total,
                page=pagination.page,
                per_page=pagination.per_page,
            ),
        )

    def resolve_wallet_history(
        self,
        info: graphene.ResolveInfo,
        investment_id: UUID,
        page: int,
        per_page: int,
    ) -> WalletHistoryPayloadType:
        _validate_pagination_values(page, per_page)
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message=(
                "Você não tem permissão para ver o histórico deste investimento."
            ),
        )

        history = investment.history or []
        sorted_history = sorted(
            history,
            key=lambda item: (
                item.get("originalQuantity", 0) or 0,
                item.get("changeDate", ""),
            ),
            reverse=True,
        )
        total = len(sorted_history)
        start = (page - 1) * per_page
        end = start + per_page
        items = sorted_history[start:end]

        pages = (total + per_page - 1) // per_page if per_page and total else 0
        mapped_items = [
            WalletHistoryItemType(
                original_quantity=item.get("originalQuantity"),
                original_value=item.get("originalValue"),
                change_type=item.get("changeType"),
                change_date=item.get("changeDate"),
            )
            for item in items
        ]
        return WalletHistoryPayloadType(
            items=mapped_items,
            pagination=PaginationType(
                total=total,
                page=page,
                per_page=per_page,
                pages=pages,
            ),
        )

    def resolve_tickers(self, info: graphene.ResolveInfo) -> list[TickerType]:
        user = get_current_user_required()
        tickers = UserTicker.query.filter_by(user_id=user.id).all()
        return [
            TickerType(
                id=str(item.id),
                symbol=item.symbol,
                quantity=item.quantity,
                type=item.type,
            )
            for item in tickers
        ]
