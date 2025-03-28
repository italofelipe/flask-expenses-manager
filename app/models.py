from app.extensions.database import db
import uuid
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import text

class User(db.Model):
    __tablename__ = 'users' 
    id = db.Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        nullable=False
    )
    name = db.Column(db.String(128), nullable=False)
    email = db.Column(db.String(128), nullable=False, unique=True)
    password = db.Column(db.String(256), nullable=False)

    def __repr__(self):
        return f"<User {self.name}>"
        