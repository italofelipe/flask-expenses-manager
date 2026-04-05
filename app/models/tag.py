# mypy: disable-error-code=name-defined

from uuid import uuid4

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db

DEFAULT_TAGS = [
    {"name": "Alimentação", "color": "#FF6B6B", "icon": "🍔"},
    {"name": "Transporte", "color": "#4ECDC4", "icon": "🚗"},
    {"name": "Moradia", "color": "#45B7D1", "icon": "🏠"},
    {"name": "Saúde", "color": "#96CEB4", "icon": "❤️"},
    {"name": "Lazer", "color": "#FFEAA7", "icon": "🎮"},
    {"name": "Educação", "color": "#DDA0DD", "icon": "📚"},
    {"name": "Investimentos", "color": "#98FB98", "icon": "📈"},
    {"name": "Outros", "color": "#D3D3D3", "icon": "📦"},
]


class Tag(db.Model):
    __tablename__ = "tags"

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(7), nullable=True)
    icon = db.Column(db.String(50), nullable=True)


def seed_default_tags(user_id: object) -> None:
    """Create the default tag set for a newly registered user."""
    from app.extensions.database import db as _db

    for tag_data in DEFAULT_TAGS:
        tag = Tag(
            user_id=user_id,
            name=tag_data["name"],
            color=tag_data["color"],
            icon=tag_data["icon"],
        )
        _db.session.add(tag)
