from __future__ import annotations

from marshmallow import Schema, fields


class EntitlementSchema(Schema):
    class Meta:
        name = "Entitlement"

    id = fields.UUID(dump_only=True)
    user_id = fields.UUID(dump_only=True)
    feature_key = fields.Str(dump_only=True)
    granted_at = fields.DateTime(dump_only=True)
    expires_at = fields.DateTime(dump_only=True, allow_none=True)
    source = fields.Method("get_source", dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    is_active = fields.Method("get_is_active", dump_only=True)

    def get_source(self, obj: object) -> str:
        from app.models.entitlement import Entitlement

        if isinstance(obj, Entitlement) and obj.source is not None:
            return str(obj.source.value)
        return ""

    def get_is_active(self, obj: object) -> bool:
        from app.models.entitlement import Entitlement
        from app.utils.datetime_utils import utc_now_naive

        if not isinstance(obj, Entitlement):
            return False
        if obj.expires_at is None:
            return True
        return bool(obj.expires_at > utc_now_naive())
