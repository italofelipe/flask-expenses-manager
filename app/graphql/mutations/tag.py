"""GraphQL mutations for the Tags domain (#1148)."""

from __future__ import annotations

import re

import graphene

from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import TagPayload, TagType
from app.models.tag import Tag

_HEX_COLOR_RE = re.compile(r"^#[0-9A-Fa-f]{6}([0-9A-Fa-f]{2})?$")


def _to_tag_type(t: Tag) -> TagType:
    return TagType(id=str(t.id), name=t.name, color=t.color, icon=t.icon)


def _normalize_color(color: str | None) -> str | None:
    if color and _HEX_COLOR_RE.match(color):
        return color[:7]
    return color


class CreateTagMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        color = graphene.String()
        icon = graphene.String()

    Output = TagPayload

    @log_graphql_resolver("createTag")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        name: str,
        color: str | None = None,
        icon: str | None = None,
    ) -> TagPayload:
        user = get_current_user_required()
        name = name.strip()
        if not name:
            raise build_public_graphql_error(
                "name is required", code="VALIDATION_ERROR"
            )
        if len(name) > 50:
            raise build_public_graphql_error(
                "name must be at most 50 characters", code="VALIDATION_ERROR"
            )
        if color and not _HEX_COLOR_RE.match(color):
            raise build_public_graphql_error(
                "color must be a valid hex code (e.g. #FF6B6B)", code="VALIDATION_ERROR"
            )
        tag = Tag(
            user_id=user.id,
            name=name,
            color=_normalize_color(color),
            icon=icon,
        )
        db.session.add(tag)
        db.session.commit()
        return TagPayload(
            ok=True,
            message="Tag criada com sucesso.",
            errors=[],
            data=_to_tag_type(tag),
        )


class UpdateTagMutation(graphene.Mutation):
    class Arguments:
        tag_id = graphene.UUID(required=True)
        name = graphene.String(required=True)
        color = graphene.String()
        icon = graphene.String()

    Output = TagPayload

    @log_graphql_resolver("updateTag")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        tag_id: object,
        name: str,
        color: str | None = None,
        icon: str | None = None,
    ) -> TagPayload:
        user = get_current_user_required()
        tag = Tag.query.filter_by(id=tag_id, user_id=user.id).first()
        if not tag:
            raise build_public_graphql_error("Tag not found", code="NOT_FOUND")
        name = name.strip()
        if not name:
            raise build_public_graphql_error(
                "name is required", code="VALIDATION_ERROR"
            )
        if len(name) > 50:
            raise build_public_graphql_error(
                "name must be at most 50 characters", code="VALIDATION_ERROR"
            )
        if color and not _HEX_COLOR_RE.match(color):
            raise build_public_graphql_error(
                "color must be a valid hex code (e.g. #FF6B6B)", code="VALIDATION_ERROR"
            )
        tag.name = name
        tag.color = _normalize_color(color)
        tag.icon = icon
        db.session.commit()
        return TagPayload(
            ok=True,
            message="Tag atualizada com sucesso.",
            errors=[],
            data=_to_tag_type(tag),
        )


class DeleteTagMutation(graphene.Mutation):
    class Arguments:
        tag_id = graphene.UUID(required=True)

    Output = TagPayload

    @log_graphql_resolver("deleteTag")
    def mutate(self, _info: graphene.ResolveInfo, tag_id: object) -> TagPayload:
        user = get_current_user_required()
        tag = Tag.query.filter_by(id=tag_id, user_id=user.id).first()
        if not tag:
            raise build_public_graphql_error("Tag not found", code="NOT_FOUND")
        db.session.delete(tag)
        db.session.commit()
        return TagPayload(ok=True, message="Tag removida com sucesso.", errors=[])
