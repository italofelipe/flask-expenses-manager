# mypy: disable-error-code="name-defined,no-redef"

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class PushTransport(str, enum.Enum):
    web_push = "web_push"
    expo = "expo"


class PushSubscription(db.Model):
    __tablename__ = "push_subscriptions"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # native_enum=False: stored as VARCHAR+CHECK constraint, no CREATE TYPE needed.
    # Avoids migration conflicts when SQLAlchemy auto-emits CREATE TYPE on connection.
    transport = db.Column(
        db.Enum(PushTransport, name="push_transport", native_enum=False), nullable=False
    )
    endpoint = db.Column(db.Text, nullable=False)
    keys = db.Column(db.JSON, nullable=True)
    expiration_time = db.Column(db.DateTime, nullable=True)
    device_label = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now_naive, nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "transport",
            "endpoint",
            name="uq_push_subscriptions_user_transport_endpoint",
        ),
    )
