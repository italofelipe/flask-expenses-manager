"""GraphQL queries for the Tags domain (#1148)."""

from __future__ import annotations

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import TagListType, TagType
from app.models.tag import Tag


def _to_tag_type(t: Tag) -> TagType:
    return TagType(id=str(t.id), name=t.name, color=t.color, icon=t.icon)


class TagQueryMixin:
    tags = graphene.Field(TagListType)
    tag = graphene.Field(TagType, tag_id=graphene.UUID(required=True))

    @log_graphql_resolver("tags")
    def resolve_tags(self, _info: graphene.ResolveInfo) -> TagListType:
        user = get_current_user_required()
        rows = Tag.query.filter_by(user_id=user.id).order_by(Tag.name).all()
        return TagListType(tags=[_to_tag_type(t) for t in rows], total=len(rows))

    @log_graphql_resolver("tag")
    def resolve_tag(
        self, _info: graphene.ResolveInfo, tag_id: object
    ) -> TagType | None:
        user = get_current_user_required()
        t = Tag.query.filter_by(id=tag_id, user_id=user.id).first()
        return _to_tag_type(t) if t else None
