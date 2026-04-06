from __future__ import annotations

from marshmallow import Schema, fields, pre_load, validate

from app.schemas.sanitization import sanitize_string_fields

BUDGET_PERIODS = ("monthly", "weekly", "custom")


class BudgetSchema(Schema):
    class Meta:
        name = "Budget"

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    tag_id = fields.UUID(allow_none=True, load_default=None)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    amount = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.01),
    )
    period = fields.Str(
        load_default="monthly",
        validate=validate.OneOf(BUDGET_PERIODS),
    )
    start_date = fields.Date(allow_none=True)
    end_date = fields.Date(allow_none=True)
    is_active = fields.Bool(load_default=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(data, {"name", "period"})
        if isinstance(sanitized, dict) and isinstance(sanitized.get("period"), str):
            sanitized["period"] = str(sanitized["period"]).lower()
        return sanitized
