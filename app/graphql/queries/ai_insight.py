from __future__ import annotations

import graphene

from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.models.ai_insight import AIInsight


class AIInsightType(graphene.ObjectType):
    id = graphene.ID(required=True)
    content = graphene.String(required=True)
    insight_type = graphene.String(required=True)
    period_label = graphene.String(required=True)
    period_start = graphene.String(required=True)
    period_end = graphene.String(required=True)
    model = graphene.String(required=True)
    tokens_used = graphene.Int(required=True)
    cost_usd = graphene.Float(required=True)
    created_at = graphene.String(required=True)


class AIInsightHistoryResultType(graphene.ObjectType):
    items = graphene.List(graphene.NonNull(AIInsightType), required=True)
    page = graphene.Int(required=True)
    per_page = graphene.Int(required=True)
    total = graphene.Int(required=True)


def _to_ai_insight_type(row: AIInsight) -> AIInsightType:
    return AIInsightType(
        id=str(row.id),
        content=row.content,
        insight_type=row.insight_type.value,
        period_label=row.period_label,
        period_start=row.period_start.isoformat() if row.period_start else "",
        period_end=row.period_end.isoformat() if row.period_end else "",
        model=row.model,
        tokens_used=row.tokens_used,
        cost_usd=float(row.cost_usd),
        created_at=row.created_at.isoformat() if row.created_at else "",
    )


class AIInsightQueryMixin:
    ai_insight_history = graphene.Field(
        AIInsightHistoryResultType,
        page=graphene.Int(default_value=1),
        per_page=graphene.Int(default_value=20),
    )

    def resolve_ai_insight_history(
        self,
        _info: graphene.ResolveInfo,
        page: int,
        per_page: int,
    ) -> AIInsightHistoryResultType:
        user = get_current_user_required()
        user_id = user.id

        total = db.session.query(AIInsight).filter_by(user_id=user_id).count()
        rows = (
            db.session.query(AIInsight)
            .filter_by(user_id=user_id)
            .order_by(AIInsight.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return AIInsightHistoryResultType(
            items=[_to_ai_insight_type(r) for r in rows],
            page=page,
            per_page=per_page,
            total=total,
        )
