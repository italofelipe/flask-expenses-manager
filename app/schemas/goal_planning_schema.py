from __future__ import annotations

from marshmallow import Schema, fields, pre_load, validate

from app.schemas.sanitization import sanitize_string_fields


class GoalSimulationSchema(Schema):
    class Meta:
        name = "GoalSimulationInput"

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
    target_date = fields.Date(allow_none=True)
    monthly_income = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0),
    )
    monthly_expenses = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0),
    )
    monthly_contribution = fields.Decimal(
        as_string=True,
        allow_none=True,
        load_default=None,
        validate=validate.Range(min=0),
    )

    @pre_load
    def sanitize_input(self, data: object, **kwargs: object) -> object:
        return sanitize_string_fields(
            data,
            {
                "target_amount",
                "current_amount",
                "monthly_income",
                "monthly_expenses",
                "monthly_contribution",
                "target_date",
            },
        )
