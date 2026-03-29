# mypy: disable-error-code="name-defined"
"""Entitlement model — J12 (subscription feature access)."""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


def _enum_values(enum_cls: type[enum.Enum]) -> list[str]:
    return [str(item.value) for item in enum_cls]


class EntitlementSource(enum.Enum):
    SUBSCRIPTION = "subscription"
    MANUAL = "manual"
    TRIAL = "trial"


class Entitlement(db.Model):
    """A feature entitlement granted to a user, optionally time-bounded."""

    __tablename__ = "entitlements"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True
    )
    feature_key = db.Column(db.String(80), nullable=False)
    granted_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    expires_at = db.Column(db.DateTime, nullable=True)
    source = db.Column(
        db.Enum(EntitlementSource, values_callable=_enum_values), nullable=False
    )
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    __table_args__ = (
        db.Index("ix_entitlements_user_feature", "user_id", "feature_key"),
        db.Index("ix_entitlements_user_expires", "user_id", "expires_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Entitlement user={self.user_id} feature={self.feature_key}"
            f" source={self.source}>"
        )
