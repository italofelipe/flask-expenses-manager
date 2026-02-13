from __future__ import annotations

from typing import Any

from app.models.wallet import Wallet
from app.schemas.wallet_schema import WalletSchema


def _strip_contract_fields(item: dict[str, Any]) -> dict[str, Any]:
    if item.get("ticker") is None:
        # hardcoded: omit ticker, quantity, and estimated value
        item.pop("estimated_value_on_create_date", None)
        item.pop("ticker", None)
        item.pop("quantity", None)
    else:
        # ticker: omit value
        item.pop("value", None)
    return item


def serialize_wallet_item(wallet: Wallet) -> dict[str, Any]:
    schema = WalletSchema()
    return _strip_contract_fields(schema.dump(wallet))


def serialize_wallet_items(items: list[Wallet]) -> list[dict[str, Any]]:
    schema = WalletSchema(many=True)
    raw = schema.dump(items)
    return [_strip_contract_fields(item) for item in raw]
