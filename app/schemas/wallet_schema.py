from typing import Any, Dict

from marshmallow import Schema, ValidationError, fields, validates_schema


class WalletSchema(Schema):
    """Schema para validação de dados da carteira de investimentos."""

    class Meta:
        """Metadados do schema."""

        name = "WalletSchema"

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    name = fields.String(required=True)
    value = fields.Decimal(as_string=True, allow_none=True)
    estimated_value_on_create_date = fields.Decimal(as_string=True, allow_none=True)
    ticker = fields.String(allow_none=True)
    quantity = fields.Integer(allow_none=True)
    register_date = fields.Date(required=True)
    target_withdraw_date = fields.Date(allow_none=True)
    should_be_on_wallet = fields.Boolean(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @validates_schema
    def validate_fields(self, data: Dict[str, Any], **kwargs: Any) -> None:
        """Valida as regras de negócio entre os campos ticker, quantity e value."""
        has_ticker = bool(data.get("ticker"))
        has_quantity = data.get("quantity") is not None
        has_value = data.get("value") is not None

        if has_ticker and not has_quantity:
            raise ValidationError(
                "O campo 'quantity' é obrigatório quando 'ticker' for informado.",
                field_name="quantity",
            )

        if has_ticker and has_value:
            raise ValidationError(
                "Não envie o campo 'value' quando usar 'ticker'. Ele será calculado.",
                field_name="value",
            )

        # Somente se nem value nem ticker forem enviados (ex: criação ou atualização sem base anterior)
        if not has_ticker and not has_value and not kwargs.get("partial", False):
            raise ValidationError(
                "Informe o campo 'value' caso não esteja usando 'ticker'.",
                field_name="value",
            )
