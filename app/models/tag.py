from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
