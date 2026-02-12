from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import graphene
from graphql import GraphQLError
from marshmallow import ValidationError

from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import (
    _get_owned_wallet_or_error,
    _wallet_to_graphql_payload,
)
from app.graphql.types import WalletType
from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema
from app.services.investment_service import InvestmentService
from app.utils.datetime_utils import iso_utc_now_naive


class AddWalletEntryMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        value = graphene.Float()
        ticker = graphene.String()
        quantity = graphene.Int()
        asset_class = graphene.String()
        annual_rate = graphene.Float()
        register_date = graphene.String()
        target_withdraw_date = graphene.String()
        should_be_on_wallet = graphene.Boolean(required=True)

    item = graphene.Field(WalletType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> "AddWalletEntryMutation":
        user = get_current_user_required()
        raw_data = {
            "name": kwargs["name"],
            "value": kwargs.get("value"),
            "ticker": kwargs.get("ticker"),
            "quantity": kwargs.get("quantity"),
            "asset_class": kwargs.get("asset_class", "custom"),
            "annual_rate": kwargs.get("annual_rate"),
            "register_date": kwargs.get("register_date") or date.today().isoformat(),
            "target_withdraw_date": kwargs.get("target_withdraw_date"),
            "should_be_on_wallet": kwargs["should_be_on_wallet"],
        }
        schema = WalletSchema()
        try:
            validated_data = schema.load(raw_data)
        except ValidationError as exc:
            raise GraphQLError(f"Dados inválidos: {exc.messages}") from exc
        estimated_value = InvestmentService.calculate_estimated_value(validated_data)
        wallet = Wallet(
            user_id=user.id,
            name=validated_data["name"],
            value=validated_data.get("value"),
            estimated_value_on_create_date=estimated_value,
            ticker=validated_data.get("ticker"),
            quantity=validated_data.get("quantity"),
            asset_class=str(validated_data.get("asset_class", "custom")).lower(),
            annual_rate=validated_data.get("annual_rate"),
            register_date=validated_data["register_date"],
            target_withdraw_date=validated_data.get("target_withdraw_date"),
            should_be_on_wallet=validated_data["should_be_on_wallet"],
        )
        db.session.add(wallet)
        db.session.commit()
        return AddWalletEntryMutation(
            item=WalletType(**_wallet_to_graphql_payload(wallet))
        )


class UpdateWalletEntryMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)
        name = graphene.String()
        value = graphene.Float()
        ticker = graphene.String()
        quantity = graphene.Int()
        asset_class = graphene.String()
        annual_rate = graphene.Float()
        register_date = graphene.String()
        target_withdraw_date = graphene.String()
        should_be_on_wallet = graphene.Boolean()

    item = graphene.Field(WalletType, required=True)

    def mutate(
        self, info: graphene.ResolveInfo, investment_id: UUID, **kwargs: Any
    ) -> "UpdateWalletEntryMutation":
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message="Você não tem permissão para editar este investimento.",
        )

        raw_payload: dict[str, Any] = {
            "name": kwargs.get("name"),
            "value": kwargs.get("value"),
            "ticker": kwargs.get("ticker"),
            "quantity": kwargs.get("quantity"),
            "asset_class": kwargs.get("asset_class"),
            "annual_rate": kwargs.get("annual_rate"),
            "register_date": kwargs.get("register_date"),
            "target_withdraw_date": kwargs.get("target_withdraw_date"),
            "should_be_on_wallet": kwargs.get("should_be_on_wallet"),
        }
        payload = {k: v for k, v in raw_payload.items() if v is not None}
        schema = WalletSchema(partial=True)
        try:
            validated_data = schema.load(payload, partial=True)
        except ValidationError as exc:
            raise GraphQLError(f"Dados inválidos: {exc.messages}") from exc

        original_quantity = investment.quantity
        original_value = investment.value
        for key, value in validated_data.items():
            if key == "asset_class":
                setattr(investment, key, str(value).lower())
            elif key in {"value", "annual_rate"} and value is not None:
                setattr(investment, key, Decimal(str(value)))
            else:
                setattr(investment, key, value)

        if investment.ticker:
            estimated_value = InvestmentService.calculate_estimated_value(
                {"ticker": investment.ticker, "quantity": investment.quantity}
            )
            investment.estimated_value_on_create_date = estimated_value

        if (
            original_quantity != investment.quantity
            or original_value != investment.value
        ):
            history = investment.history or []
            history.append(
                {
                    "originalQuantity": original_quantity,
                    "originalValue": (
                        float(original_value) if original_value is not None else None
                    ),
                    "newQuantity": investment.quantity,
                    "newValue": (
                        float(investment.value)
                        if investment.value is not None
                        else None
                    ),
                    "changeType": "update",
                    "changeDate": iso_utc_now_naive(),
                }
            )
            investment.history = history

        db.session.commit()
        return UpdateWalletEntryMutation(
            item=WalletType(**_wallet_to_graphql_payload(investment))
        )


class DeleteWalletEntryMutation(graphene.Mutation):
    class Arguments:
        investment_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, investment_id: UUID
    ) -> "DeleteWalletEntryMutation":
        user = get_current_user_required()
        investment = _get_owned_wallet_or_error(
            investment_id,
            user.id,
            forbidden_message="Você não tem permissão para remover este investimento.",
        )
        db.session.delete(investment)
        db.session.commit()
        return DeleteWalletEntryMutation(
            ok=True, message="Investimento removido com sucesso"
        )
