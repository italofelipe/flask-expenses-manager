# mypy: disable-error-code=name-defined
"""RefreshToken model — one row per active device session.

Each row represents a single session (one device / browser / client). On
token rotation a new row is created and the old one is revoked.

Token-theft detection via ``family_id``:
- All rows originating from the same login share the same ``family_id``.
- If a already-revoked token is presented for rotation, the entire family is
  revoked (family-wide invalidation).
"""

from __future__ import annotations

import uuid

from sqlalchemy.dialects.postgresql import JSON, UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive

_MAX_SESSIONS_PER_USER = 5  # configurable via env in the service layer


class RefreshToken(db.Model):
    __tablename__ = "refresh_tokens"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # SHA-256 hex digest of the raw token — never store the token itself.
    token_hash = db.Column(db.String(64), nullable=False, unique=True, index=True)
    # JTI embedded in the JWT so revocation can also be checked by JTI.
    jti = db.Column(db.String(128), nullable=False, unique=True, index=True)
    # JTI of the *access token* issued alongside this refresh token.
    # Allows per-session access-token revocation without a global current_jti.
    current_access_jti = db.Column(db.String(128), nullable=True)
    # Family of tokens that share the same login lineage (for theft detection).
    family_id = db.Column(UUID(as_uuid=True), nullable=False, index=True)
    # Human-readable device info (user-agent + partial IP) — stored as JSON.
    device_info = db.Column(JSON, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)

    user = db.relationship("User", backref=db.backref("refresh_tokens", lazy="dynamic"))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        return self.revoked_at is None and self.expires_at > utc_now_naive()

    def revoke(self) -> None:
        self.revoked_at = utc_now_naive()

    def __repr__(self) -> str:
        status = "active" if self.is_active else "revoked"
        return f"<RefreshToken {self.id} user={self.user_id} {status}>"


__all__ = ["RefreshToken", "_MAX_SESSIONS_PER_USER"]
