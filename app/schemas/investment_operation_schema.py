from datetime import date
from decimal import Decimal
from typing import Any, Dict

from marshmallow import Schema, ValidationError, fields, validates_schema


class InvestmentOperationSchema(Schema):
    id = fields.UUID(dump_only=True)
    wallet_id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    operation_type = fields.String(required=True)
    quantity = fields.Decimal(required=True, as_string=True)
    unit_price = fields.Decimal(required=True, as_string=True)
    fees = fields.Decimal(load_default=Decimal("0"), as_string=True)
    executed_at = fields.Date(load_default=lambda: date.today())
    notes = fields.String(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema  # type: ignore[misc]
    def validate_business_rules(self, data: Dict[str, Any], **kwargs: Any) -> None:
        is_partial = bool(kwargs.get("partial", False))
        operation_type = str(data.get("operation_type", "")).strip().lower()
        quantity = data.get("quantity")
        unit_price = data.get("unit_price")
        fees = data.get("fees")

        if (not is_partial or "operation_type" in data) and (
            operation_type not in {"buy", "sell"}
        ):
            raise ValidationError(
                "Campo 'operation_type' inválido. Use 'buy' ou 'sell'.",
                field_name="operation_type",
            )

        if (not is_partial or "quantity" in data) and (
            quantity is None or Decimal(str(quantity)) <= 0
        ):
            raise ValidationError(
                "Campo 'quantity' deve ser maior que zero.",
                field_name="quantity",
            )

        if (not is_partial or "unit_price" in data) and (
            unit_price is None or Decimal(str(unit_price)) <= 0
        ):
            raise ValidationError(
                "Campo 'unit_price' deve ser maior que zero.",
                field_name="unit_price",
            )

        if fees is not None and Decimal(str(fees)) < 0:
            raise ValidationError(
                "Campo 'fees' não pode ser negativo.",
                field_name="fees",
            )
