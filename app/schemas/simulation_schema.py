from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validate, validates

from app.simulations.tools_registry import TOOLS_REGISTRY, sorted_tool_ids


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
        validate=validate.Length(min=1, max=32),
    )
    inputs = fields.Dict(required=True)
    result = fields.Dict(required=True)
    # The DB column is named ``metadata``; the Python attribute is
    # ``extra_metadata`` to avoid colliding with SQLAlchemy's reserved
    # ``Model.metadata``.
    extra_metadata = fields.Dict(
        data_key="metadata",
        attribute="extra_metadata",
        allow_none=True,
        load_default=None,
    )
    saved = fields.Bool(dump_default=False)
    goal_id = fields.UUID(allow_none=True)
    created_at = fields.DateTime(dump_only=True)

    @validates("tool_id")
    def _validate_tool_id(self, value: str, **_: object) -> None:
        if value not in TOOLS_REGISTRY:
            raise ValidationError(
                f"tool_id '{value}' is not in the canonical registry. "
                f"Known tools: {', '.join(sorted_tool_ids())}.",
            )

    @validates("inputs")
    def _validate_inputs(self, value: object, **_: object) -> None:
        if not isinstance(value, dict):
            raise ValidationError("inputs must be a JSON object.")

    @validates("result")
    def _validate_result(self, value: object, **_: object) -> None:
        if not isinstance(value, dict):
            raise ValidationError("result must be a JSON object.")

    @validates("extra_metadata")
    def _validate_metadata(self, value: object, **_: object) -> None:
        if value is None:
            return
        if not isinstance(value, dict):
            raise ValidationError("metadata must be a JSON object when present.")
