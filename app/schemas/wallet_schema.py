from datetime import date
from typing import Any, Dict

from marshmallow import Schema, ValidationError, fields, pre_load, validates_schema

from app.schemas.sanitization import sanitize_string_fields

ASSET_CLASSES = {
    "custom",
    "stock",
    "fii",
    "etf",
    "bdr",
    "crypto",
    "cdb",
    "cdi",
    "lci",
    "lca",
    "tesouro",
    "fund",
}
MARKET_ASSET_CLASSES = {"stock", "fii", "etf", "bdr", "crypto"}
FIXED_INCOME_ASSET_CLASSES = {"cdb", "cdi", "lci", "lca", "tesouro"}


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
    asset_class = fields.String(allow_none=True)
    annual_rate = fields.Decimal(as_string=True, allow_none=True)
    register_date = fields.Date(missing=lambda: date.today())
    target_withdraw_date = fields.Date(allow_none=True)
    should_be_on_wallet = fields.Boolean(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @pre_load  # type: ignore[misc]
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"name", "ticker", "asset_class"})
        if isinstance(sanitized, dict):
            if isinstance(sanitized.get("ticker"), str):
                sanitized["ticker"] = str(sanitized["ticker"]).upper()
            if isinstance(sanitized.get("asset_class"), str):
                sanitized["asset_class"] = str(sanitized["asset_class"]).lower()
        return sanitized

    @validates_schema  # type: ignore[misc]
    def validate_fields(self, data: Dict[str, Any], **kwargs: Any) -> None:
        """Valida as regras de negócio entre os campos ticker, quantity e value."""
        has_ticker = bool(data.get("ticker"))
        has_quantity = data.get("quantity") is not None
        has_value = data.get("value") is not None
        asset_class = str(data.get("asset_class") or "custom").strip().lower()
        annual_rate = data.get("annual_rate")

        if asset_class not in ASSET_CLASSES:
            raise ValidationError(
                "Campo 'asset_class' inválido.",
                field_name="asset_class",
            )

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

        # Somente se nem value nem ticker forem enviados
        # (ex: criação ou atualização sem base anterior)
        if not has_ticker and not has_value and not kwargs.get("partial", False):
            raise ValidationError(
                "Informe o campo 'value' caso não esteja usando 'ticker'.",
                field_name="value",
            )

        if asset_class in MARKET_ASSET_CLASSES and not has_ticker:
            raise ValidationError(
                "Para classes de mercado (stock/fii/etf/bdr/crypto), informe 'ticker'.",
                field_name="ticker",
            )

        if asset_class in FIXED_INCOME_ASSET_CLASSES and annual_rate is None:
            raise ValidationError(
                "Campo 'annual_rate' é obrigatório para ativos de renda fixa.",
                field_name="annual_rate",
            )
