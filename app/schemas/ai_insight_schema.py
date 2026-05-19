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
    preview_run_id = fields.UUID(
        required=False,
        allow_none=True,
        metadata={
            "description": (
                "Run de preview admin a ser reutilizado para manter o mesmo "
                "snapshot_hash na geração."
            ),
            "example": "550e8400-e29b-41d4-a716-446655440000",
        },
    )


__all__ = ["AIInsightGenerateRequestSchema"]
