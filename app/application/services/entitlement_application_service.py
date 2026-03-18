"""Application service for Entitlement queries (J7)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.models.entitlement import Entitlement
from app.schemas.entitlement_schema import EntitlementSchema
from app.services.entitlement_service import EntitlementService


class EntitlementApplicationService:
    def __init__(self, *, user_id: UUID) -> None:
        self._user_id = user_id
        self._service = EntitlementService(user_id)
        self._schema = EntitlementSchema()

    @classmethod
    def with_defaults(cls, user_id: UUID) -> EntitlementApplicationService:
        return cls(user_id=user_id)

    def _serialize(self, ent: Entitlement) -> dict[str, Any]:
        return dict(self._schema.dump(ent))

    def list_entitlements(self) -> list[dict[str, Any]]:
        ents = self._service.list_entitlements()
        return [self._serialize(e) for e in ents]

    def check_entitlement(self, feature_key: str) -> dict[str, Any]:
        active = self._service.check_entitlement(feature_key)
        return {
            "feature_key": feature_key,
            "active": active,
        }
