from __future__ import annotations

import graphene

from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.errors import (
    GRAPHQL_ERROR_CODE_CONFLICT,
    GRAPHQL_ERROR_CODE_NOT_FOUND,
    build_public_graphql_error,
)
from app.graphql.types import TickerType
from app.models.user_ticker import UserTicker


class AddTickerMutation(graphene.Mutation):
    class Arguments:
        symbol = graphene.String(required=True)
        quantity = graphene.Float(required=True)
        type = graphene.String()

    item = graphene.Field(TickerType, required=True)

    def mutate(
        self,
        info: graphene.ResolveInfo,
        symbol: str,
        quantity: float,
        type: str | None = None,
    ) -> "AddTickerMutation":
        user = get_current_user_required()
        normalized_symbol = symbol.upper()
        exists = UserTicker.query.filter_by(
            user_id=user.id, symbol=normalized_symbol
        ).first()
        if exists:
            raise build_public_graphql_error(
                "Ticker já adicionado",
                code=GRAPHQL_ERROR_CODE_CONFLICT,
            )
        ticker = UserTicker(
            symbol=normalized_symbol,
            quantity=quantity,
            type=type,
            user_id=user.id,
        )
        db.session.add(ticker)
        db.session.commit()
        return AddTickerMutation(
            item=TickerType(
                id=str(ticker.id),
                symbol=ticker.symbol,
                quantity=ticker.quantity,
                type=ticker.type,
            )
        )


class DeleteTickerMutation(graphene.Mutation):
    class Arguments:
        symbol = graphene.String(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(self, info: graphene.ResolveInfo, symbol: str) -> "DeleteTickerMutation":
        user = get_current_user_required()
        ticker = UserTicker.query.filter_by(
            user_id=user.id, symbol=symbol.upper()
        ).first()
        if not ticker:
            raise build_public_graphql_error(
                "Ticker não encontrado",
                code=GRAPHQL_ERROR_CODE_NOT_FOUND,
            )
        db.session.delete(ticker)
        db.session.commit()
        return DeleteTickerMutation(ok=True, message="Ticker removido com sucesso")
