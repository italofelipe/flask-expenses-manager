from __future__ import annotations

from datetime import date

from marshmallow import (
    Schema,
    ValidationError,
    fields,
    pre_load,
    validate,
    validates_schema,
)

from app.schemas.sanitization import sanitize_string_fields

RATE_TYPES = ("manual", "product_default", "inflation_only")
RECOMMENDED_OPTIONS = ("cash", "installment", "equivalent")
TRANSACTION_STATUSES = ("pending", "paid", "cancelled", "postponed", "overdue")


class InstallmentVsCashCalculationSchema(Schema):
    class Meta:
        name = "InstallmentVsCashCalculation"

    cash_price = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.01),
    )
    installment_count = fields.Int(
        required=True,
        validate=validate.Range(min=1, max=60),
    )
    installment_amount = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0.01),
    )
    installment_total = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0.01),
    )
    first_payment_delay_days = fields.Int(
        load_default=30,
        validate=validate.Range(min=0, max=3650),
    )
    opportunity_rate_type = fields.Str(
        load_default="manual",
        validate=validate.OneOf(RATE_TYPES),
    )
    opportunity_rate_annual = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0, max=1000),
    )
    inflation_rate_annual = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0, max=1000),
    )
    fees_enabled = fields.Bool(load_default=False)
    fees_upfront = fields.Decimal(
        as_string=True,
        load_default="0.00",
        validate=validate.Range(min=0),
    )
    scenario_label = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=120),
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data,
            {"opportunity_rate_type", "scenario_label"},
        )
        if isinstance(sanitized, dict):
            if isinstance(sanitized.get("opportunity_rate_type"), str):
                sanitized["opportunity_rate_type"] = str(
                    sanitized["opportunity_rate_type"]
                ).lower()
            if not sanitized.get("fees_enabled"):
                sanitized["fees_upfront"] = "0.00"
        return sanitized

    @validates_schema
    def validate_payload(self, data: dict[str, object], **kwargs: object) -> None:
        installment_amount = data.get("installment_amount")
        installment_total = data.get("installment_total")
        if installment_amount is None and installment_total is None:
            raise ValidationError(
                "Informe installment_amount ou installment_total.",
                field_name="installment_amount",
            )

        if (
            data.get("opportunity_rate_type") == "manual"
            and data.get("opportunity_rate_annual") is None
        ):
            raise ValidationError(
                (
                    "opportunity_rate_annual é obrigatório quando "
                    "opportunity_rate_type=manual."
                ),
                field_name="opportunity_rate_annual",
            )


class InstallmentVsCashSaveSchema(InstallmentVsCashCalculationSchema):
    class Meta:
        name = "InstallmentVsCashSave"


class InstallmentVsCashGoalBridgeSchema(Schema):
    class Meta:
        name = "InstallmentVsCashGoalBridge"

    title = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    selected_option = fields.Str(
        required=True,
        validate=validate.OneOf(RECOMMENDED_OPTIONS[:-1]),
    )
    description = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=500),
    )
    category = fields.Str(
        allow_none=True,
        load_default="planned_purchase",
        validate=validate.Length(max=64),
    )
    target_date = fields.Date(allow_none=True, load_default=None)
    priority = fields.Int(
        load_default=3,
        validate=validate.Range(min=1, max=5),
    )
    current_amount = fields.Decimal(
        as_string=True,
        load_default="0.00",
        validate=validate.Range(min=0),
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data,
            {"title", "selected_option", "description", "category"},
        )
        if isinstance(sanitized, dict):
            _normalize_date_like_field(sanitized, "target_date")
        return sanitized


class InstallmentVsCashPlannedExpenseBridgeSchema(Schema):
    class Meta:
        name = "InstallmentVsCashPlannedExpenseBridge"

    title = fields.Str(required=True, validate=validate.Length(min=1, max=120))
    selected_option = fields.Str(
        required=True,
        validate=validate.OneOf(RECOMMENDED_OPTIONS[:-1]),
    )
    description = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=300),
    )
    observation = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=500),
    )
    due_date = fields.Date(allow_none=True, load_default=None)
    first_due_date = fields.Date(allow_none=True, load_default=None)
    upfront_due_date = fields.Date(allow_none=True, load_default=None)
    tag_id = fields.UUID(allow_none=True, load_default=None)
    account_id = fields.UUID(allow_none=True, load_default=None)
    credit_card_id = fields.UUID(allow_none=True, load_default=None)
    currency = fields.Str(
        load_default="BRL",
        validate=validate.Length(equal=3),
    )
    status = fields.Str(
        load_default="pending",
        validate=validate.OneOf(TRANSACTION_STATUSES),
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data,
            {
                "title",
                "selected_option",
                "description",
                "observation",
                "currency",
                "status",
            },
        )
        if isinstance(sanitized, dict):
            if isinstance(sanitized.get("selected_option"), str):
                sanitized["selected_option"] = str(sanitized["selected_option"]).lower()
            if isinstance(sanitized.get("status"), str):
                sanitized["status"] = str(sanitized["status"]).lower()
            if isinstance(sanitized.get("currency"), str):
                sanitized["currency"] = str(sanitized["currency"]).upper()
            _normalize_date_like_field(sanitized, "due_date")
            _normalize_date_like_field(sanitized, "first_due_date")
            _normalize_date_like_field(sanitized, "upfront_due_date")
        return sanitized

    @validates_schema
    def validate_dates(self, data: dict[str, object], **kwargs: object) -> None:
        selected_option = data.get("selected_option")
        if selected_option == "cash" and data.get("due_date") is None:
            raise ValidationError(
                (
                    "due_date é obrigatório para converter a opção à vista "
                    "em despesa planejada."
                ),
                field_name="due_date",
            )
        if selected_option == "installment" and data.get("first_due_date") is None:
            raise ValidationError(
                (
                    "first_due_date é obrigatório para converter a opção "
                    "parcelada em despesa planejada."
                ),
                field_name="first_due_date",
            )


def _normalize_date_like_field(payload: dict[str, object], field_name: str) -> None:
    value = payload.get(field_name)
    if isinstance(value, date):
        payload[field_name] = value.isoformat()
