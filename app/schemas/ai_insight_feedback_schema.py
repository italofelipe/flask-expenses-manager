"""Marshmallow schema for AI insight feedback (#1387)."""

from __future__ import annotations

from marshmallow import Schema, fields, validate


def _rating(description: str, example: int) -> fields.Int:
    return fields.Int(
        required=True,
        validate=validate.Range(min=0, max=5),
        metadata={"description": description, "example": example},
    )


class AIInsightFeedbackSchema(Schema):
    """Validates the POST /ai/insights/<id>/feedback body."""

    class Meta:
        name = "AIInsightFeedback"

    relevance = _rating("Relevância do insight (0–5)", 5)
    truthfulness = _rating("Veracidade do insight (0–5)", 4)
    depth = _rating("Profundidade do insight (0–5)", 4)
    usefulness = _rating("Utilidade do insight (0–5)", 5)
    comment = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=1000),
        metadata={"description": "Comentário livre (opcional)"},
    )
