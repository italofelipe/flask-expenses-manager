from __future__ import annotations

from marshmallow import Schema, fields, validate


class SimulationSchema(Schema):
    class Meta:
        name = "Simulation"

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    tool_id = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=60),
    )
    rule_version = fields.Str(
        required=True,
        validate=validate.Length(min=1, max=20),
    )
    inputs = fields.Dict(required=True)
    result = fields.Dict(required=True)
    saved = fields.Bool(dump_default=False)
    goal_id = fields.UUID(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
