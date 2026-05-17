from __future__ import annotations

from marshmallow import Schema, fields, validate


class AIInsightGenerateRequestSchema(Schema):
    period_type = fields.String(
        required=True,
        validate=validate.OneOf(["daily", "weekly", "monthly"]),
        metadata={
            "description": "Granularidade do insight financeiro.",
            "example": "daily",
        },
    )
    anchor_date = fields.Date(
        required=False,
        allow_none=True,
        metadata={
            "description": "Data âncora do período no formato YYYY-MM-DD.",
            "example": "2026-05-17",
        },
    )


__all__ = ["AIInsightGenerateRequestSchema"]
