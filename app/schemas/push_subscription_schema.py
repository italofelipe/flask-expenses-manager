"""Marshmallow schemas for push subscription registration."""

from __future__ import annotations

from marshmallow import Schema, ValidationError, fields, validates_schema


class SubscribeSchema(Schema):
    transport = fields.String(required=True)
    endpoint = fields.String(required=True)
    device_label = fields.String(load_default=None)
    expiration_time = fields.DateTime(load_default=None, allow_none=True)
    # Web Push only
    keys = fields.Dict(keys=fields.String(), values=fields.String(), load_default=None)

    @validates_schema
    def validate_transport_fields(self, data: dict[str, str], **_: object) -> None:
        transport = data.get("transport", "")
        if transport not in ("web_push", "expo"):
            raise ValidationError(
                f"transport must be 'web_push' or 'expo', got '{transport}'.",
                field_name="transport",
            )
        if transport == "web_push":
            keys = data.get("keys")
            if not keys or "p256dh" not in keys or "auth" not in keys:
                raise ValidationError(
                    "web_push transport requires 'keys' with 'p256dh' and 'auth'.",
                    field_name="keys",
                )
        if transport == "expo":
            endpoint = data.get("endpoint", "")
            if not endpoint.startswith("ExponentPushToken["):
                raise ValidationError(
                    "expo transport requires endpoint to be an ExponentPushToken.",
                    field_name="endpoint",
                )


class UnsubscribeSchema(Schema):
    endpoint = fields.String(required=True)
