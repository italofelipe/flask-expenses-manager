from __future__ import annotations

from typing import Any, NoReturn

from app.application.services.wallet_application_service import WalletApplicationError
from app.graphql.errors import build_public_graphql_error, to_public_graphql_code
from app.graphql.types import WalletHistoryItemType, WalletType

_WALLET_GRAPHQL_FIELDS = {
    "id",
    "name",
    "value",
    "estimated_value_on_create_date",
    "ticker",
    "quantity",
    "asset_class",
    "annual_rate",
    "register_date",
    "target_withdraw_date",
    "should_be_on_wallet",
}


def raise_wallet_graphql_error(exc: WalletApplicationError) -> NoReturn:
    raise build_public_graphql_error(
        exc.message,
        code=to_public_graphql_code(exc.code),
    ) from exc


def to_wallet_type(wallet_data: dict[str, Any]) -> WalletType:
    payload = {
        key: value
        for key, value in wallet_data.items()
        if key in _WALLET_GRAPHQL_FIELDS
    }
    return WalletType(**payload)


def to_wallet_history_item(history_data: dict[str, Any]) -> WalletHistoryItemType:
    return WalletHistoryItemType(
        original_quantity=history_data.get(
            "originalQuantity",
            history_data.get("original_quantity"),
        ),
        original_value=history_data.get(
            "originalValue",
            history_data.get("original_value"),
        ),
        change_type=history_data.get("changeType", history_data.get("change_type")),
        change_date=history_data.get("changeDate", history_data.get("change_date")),
    )
