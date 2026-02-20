from __future__ import annotations

from marshmallow import Schema, fields, pre_load, validate

from app.schemas.sanitization import sanitize_string_fields

GOAL_STATUSES = ("active", "completed", "paused", "cancelled")


class GoalSchema(Schema):
    class Meta:
        name = "Goal"

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    title = fields.Str(required=True, validate=validate.Length(min=1, max=128))
    description = fields.Str(validate=validate.Length(max=500))
    category = fields.Str(validate=validate.Length(max=64))
    target_amount = fields.Decimal(
        as_string=True,
        required=True,
        validate=validate.Range(min=0.01),
    )
    current_amount = fields.Decimal(
        as_string=True,
        load_default="0.00",
        validate=validate.Range(min=0),
    )
    priority = fields.Int(load_default=3, validate=validate.Range(min=1, max=5))
    target_date = fields.Date(allow_none=True)
    status = fields.Str(
        load_default="active",
        validate=validate.OneOf(GOAL_STATUSES),
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        sanitized = sanitize_string_fields(
            data,
            {"title", "description", "category", "status"},
        )
        if isinstance(sanitized, dict) and isinstance(sanitized.get("status"), str):
            sanitized["status"] = str(sanitized["status"]).lower()
        return sanitized
