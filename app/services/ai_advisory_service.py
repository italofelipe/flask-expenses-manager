"""AI Advisory Service — central service for LLM-powered financial analysis.

Provides three advisory capabilities:
  1. generate_spending_insights  — monthly spending analysis in PT-BR
  2. generate_goal_projection_narrative — narrative for a specific goal projection
  3. generate_weekly_summary_narrative — narrative for weekly summary data

All calls are logged to LLMAuditLog for cost tracking and auditability.

Required env vars (configure in .env — never set here):
  - LLM_PROVIDER: "openai" | "claude" | "stub"
  - OPENAI_API_KEY: required when LLM_PROVIDER=openai
  - ANTHROPIC_API_KEY: required when LLM_PROVIDER=claude
"""

from __future__ import annotations

import json
import logging
from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import case, func

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.goal_contribution import GoalContribution
from app.models.llm_audit_log import LLMAuditLog
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.goal_projection_service import GoalProjectionService
from app.services.llm_provider import LLMProvider, LLMProviderError, get_llm_provider
from app.services.weekly_summary import compute_weekly_summary

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AIInsight persistence helpers
# ---------------------------------------------------------------------------


def _get_cached_insight(
    *,
    user_id: UUID,
    insight_type: InsightType,
    period_label: str,
) -> AIInsight | None:
    """Return an existing AIInsight for this user/type/period, or None."""
    return (
        db.session.query(AIInsight)
        .filter_by(
            user_id=user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        .first()
    )


def _get_latest_insight(*, user_id: UUID) -> AIInsight | None:
    """Return the most recently created AIInsight for this user, or None."""
    return (
        db.session.query(AIInsight)
        .filter_by(user_id=user_id)
        .order_by(AIInsight.created_at.desc())
        .first()
    )


def _save_insight(
    *,
    user_id: UUID,
    content: str,
    insight_type: InsightType,
    period_label: str,
    period_start: date,
    period_end: date,
    model: str,
    tokens_used: int,
    cost_usd: float,
    previous_insight_id: UUID | None,
) -> AIInsight:
    """Persist a new AIInsight record and return it."""
    from decimal import Decimal as _Decimal

    insight = AIInsight(
        user_id=user_id,
        content=content,
        insight_type=insight_type,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        model=model,
        tokens_used=tokens_used,
        cost_usd=_Decimal(str(cost_usd)),
        previous_insight_id=previous_insight_id,
    )
    db.session.add(insight)
    db.session.commit()
    return insight


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _log_llm_call(
    *,
    user_id: UUID,
    endpoint: str,
    prompt: str,
    llm_response: Any,
) -> None:
    """Persist an LLMAuditLog row for every LLM call. Swallows exceptions so
    that audit failures never break the advisory flow."""
    try:
        log_row = LLMAuditLog(
            user_id=user_id,
            endpoint=endpoint,
            model=llm_response.model,
            prompt=prompt,
            response_text=llm_response.content,
            prompt_tokens=llm_response.prompt_tokens,
            completion_tokens=llm_response.completion_tokens,
            total_tokens=llm_response.total_tokens,
            estimated_cost_usd=llm_response.estimated_cost_usd,
            latency_ms=llm_response.latency_ms,
        )
        db.session.add(log_row)
        db.session.commit()
    except Exception as exc:
        log.warning(
            "ai_advisory.audit_log_failed user=%s endpoint=%s error=%s",
            user_id,
            endpoint,
            exc,
        )
        db.session.rollback()


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class AIAdvisoryService:
    """Central service for LLM-powered financial insights.

    Instantiate with a user_id. The provider defaults to whatever is
    configured in LLM_PROVIDER env var (stub in tests, openai in prod).
    """

    def __init__(
        self,
        user_id: UUID,
        llm_provider: LLMProvider | None = None,
    ) -> None:
        self._user_id = user_id
        self._provider = llm_provider or get_llm_provider()

    # ------------------------------------------------------------------
    # 1. Spending insights
    # ------------------------------------------------------------------

    def generate_spending_insights(self, month: str | None = None) -> dict[str, Any]:
        """Analyse spending for the given month and return AI-generated insights.

        Idempotent: if an insight for today already exists, returns it without
        calling the LLM. On the last calendar day of the month, generates a
        comprehensive recap (InsightType.recap) instead of a daily insight.
        The previous insight is injected into the prompt so the LLM can track
        what changed since the last generation.

        Args:
            month: "YYYY-MM" string. Defaults to the current calendar month.

        Returns:
            {"insights": str, "tokens_used": int, "cost_usd": float,
             "month": "YYYY-MM", "model": str, "cached": bool}
        """
        today = date.today()
        if month:
            year, mon = int(month[:4]), int(month[5:7])
        else:
            year, mon = today.year, today.month

        start = date(year, mon, 1)
        end = date(year, mon, monthrange(year, mon)[1])

        is_recap = today == end
        insight_type = InsightType.recap if is_recap else InsightType.daily
        period_label = (
            f"{year}-{mon:02d}-recap" if is_recap else today.strftime("%Y-%m-%d")
        )

        # Idempotency: return cached insight if already generated today
        cached = _get_cached_insight(
            user_id=self._user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        if cached is not None:
            return {
                "insights": cached.content,
                "tokens_used": cached.tokens_used,
                "cost_usd": float(cached.cost_usd),
                "month": f"{year}-{mon:02d}",
                "model": cached.model,
                "cached": True,
            }

        # Context: fetch most recent previous insight for this user
        previous = _get_latest_insight(user_id=self._user_id)
        previous_content = previous.content if previous else None

        snapshot = self._build_spending_snapshot(start=start, end=end)

        goals_ctx = _build_goals_snapshot(
            user_id=self._user_id,
            monthly_savings_brl=snapshot["balance"],
        )
        budget_ctx = _build_overall_budget_snapshot(
            user_id=self._user_id,
            total_expense_brl=snapshot["total_expense"],
        )

        prompt = _build_spending_prompt(
            snapshot,
            month_label=f"{year}-{mon:02d}",
            previous_insight=previous_content,
            is_recap=is_recap,
            goals=goals_ctx,
            budget=budget_ctx,
        )

        try:
            llm_resp = self._provider.generate_with_usage(prompt)
        except LLMProviderError as exc:
            log.warning(
                "ai_advisory.spending_insights.llm_error user=%s error=%s",
                self._user_id,
                exc,
            )
            raise

        _log_llm_call(
            user_id=self._user_id,
            endpoint="spending_insights",
            prompt=prompt,
            llm_response=llm_resp,
        )

        _save_insight(
            user_id=self._user_id,
            content=llm_resp.content,
            insight_type=insight_type,
            period_label=period_label,
            period_start=start,
            period_end=end,
            model=llm_resp.model,
            tokens_used=llm_resp.total_tokens,
            cost_usd=llm_resp.estimated_cost_usd,
            previous_insight_id=previous.id if previous else None,
        )

        return {
            "insights": llm_resp.content,
            "tokens_used": llm_resp.total_tokens,
            "cost_usd": llm_resp.estimated_cost_usd,
            "month": f"{year}-{mon:02d}",
            "model": llm_resp.model,
            "cached": False,
        }

    def _build_spending_snapshot(self, *, start: date, end: date) -> dict[str, Any]:
        """Build a spending summary dict for the given date range."""
        row = (
            db.session.query(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type == TransactionType.EXPENSE,
                                Transaction.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_expense"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type == TransactionType.INCOME,
                                Transaction.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_income"),
                func.count(Transaction.id).label("tx_count"),
            )
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.status == TransactionStatus.PAID,
                Transaction.due_date >= start,
                Transaction.due_date <= end,
            )
            .one()
        )

        # Top expense categories (tags)
        category_rows = (
            db.session.query(
                Transaction.description.label("description"),
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == TransactionStatus.PAID,
                Transaction.due_date >= start,
                Transaction.due_date <= end,
            )
            .group_by(Transaction.description)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(5)
            .all()
        )

        top_expenses = [
            {
                "description": r.description or "Sem descrição",
                "total": _safe_float(r.total),
            }
            for r in category_rows
        ]

        total_expense = _safe_float(row.total_expense)
        total_income = _safe_float(row.total_income)
        balance = round(total_income - total_expense, 2)
        savings_rate = (
            round((total_income - total_expense) / total_income * 100, 1)
            if total_income > 0
            else 0.0
        )

        return {
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "total_expense": round(total_expense, 2),
            "total_income": round(total_income, 2),
            "balance": balance,
            "savings_rate_pct": savings_rate,
            "transaction_count": int(row.tx_count or 0),
            "top_expenses": top_expenses,
        }

    # ------------------------------------------------------------------
    # 2. Goal projection narrative
    # ------------------------------------------------------------------

    def generate_goal_projection_narrative(
        self,
        goal_id: UUID,
        user_context: str,
        monthly_contribution: Decimal,
    ) -> dict[str, Any]:
        """Generate a narrative for the given goal's projection.

        Args:
            goal_id: UUID of the Goal record.
            user_context: Free-text context from the user (motivations, constraints).
            monthly_contribution: Planned monthly contribution in BRL.

        Returns:
            {"narrative": str, "tokens_used": int, "cost_usd": float,
             "projection": dict, "model": str}

        Raises:
            ValueError: When goal is not found or doesn't belong to the user.
            LLMProviderError: On provider failure.
        """
        goal: Goal | None = Goal.query.filter_by(
            id=goal_id, user_id=self._user_id
        ).first()
        if goal is None:
            raise ValueError(f"Goal {goal_id} not found for user {self._user_id}")

        projection_service = GoalProjectionService(
            monthly_contribution=monthly_contribution
        )
        projection = projection_service.project(
            goal_id=goal.id,
            user_id=self._user_id,
            current_amount=Decimal(str(goal.current_amount or 0)),
            target_amount=Decimal(str(goal.target_amount or 0)),
            target_date=goal.target_date,
        )
        projection_data = projection_service.serialize(projection)

        prompt = _build_goal_projection_prompt(
            goal_title=str(goal.title),
            projection=projection_data,
            user_context=user_context,
            monthly_contribution=monthly_contribution,
        )

        try:
            llm_resp = self._provider.generate_with_usage(prompt)
        except LLMProviderError as exc:
            log.warning(
                "ai_advisory.goal_projection.llm_error user=%s goal=%s error=%s",
                self._user_id,
                goal_id,
                exc,
            )
            raise

        _log_llm_call(
            user_id=self._user_id,
            endpoint="goal_projection",
            prompt=prompt,
            llm_response=llm_resp,
        )

        return {
            "narrative": llm_resp.content,
            "tokens_used": llm_resp.total_tokens,
            "cost_usd": llm_resp.estimated_cost_usd,
            "projection": projection_data,
            "model": llm_resp.model,
        }

    # ------------------------------------------------------------------
    # 3. Weekly summary narrative
    # ------------------------------------------------------------------

    def generate_weekly_summary_narrative(self) -> dict[str, Any]:
        """Generate a narrative for the current week's financial summary.

        Returns:
            {"narrative": str, "tokens_used": int, "cost_usd": float,
             "summary": dict, "model": str}

        Raises:
            LLMProviderError: On provider failure.
        """
        summary = compute_weekly_summary(user_id=self._user_id)
        prompt = _build_weekly_summary_prompt(summary)

        try:
            llm_resp = self._provider.generate_with_usage(prompt)
        except LLMProviderError as exc:
            log.warning(
                "ai_advisory.weekly_summary.llm_error user=%s error=%s",
                self._user_id,
                exc,
            )
            raise

        _log_llm_call(
            user_id=self._user_id,
            endpoint="weekly_summary",
            prompt=prompt,
            llm_response=llm_resp,
        )

        return {
            "narrative": llm_resp.content,
            "tokens_used": llm_resp.total_tokens,
            "cost_usd": llm_resp.estimated_cost_usd,
            "summary": summary,
            "model": llm_resp.model,
        }


# ---------------------------------------------------------------------------
# Cross-domain context helpers
# ---------------------------------------------------------------------------

_THIRTY_DAYS_AGO_DELTA = relativedelta(days=30)


def _build_goals_snapshot(
    *,
    user_id: UUID,
    monthly_savings_brl: float,
) -> list[dict[str, Any]]:
    """Return a snapshot of active goals with projection data and recent contributions.

    Uses the current month's savings as a proxy for monthly_contribution,
    distributed equally across all active goals (monthly_savings / num_goals).
    """
    goals = (
        db.session.query(Goal)
        .filter_by(user_id=user_id, status="active")
        .order_by(Goal.priority, Goal.created_at)
        .all()
    )
    if not goals:
        return []

    today = date.today()
    cutoff = today - _THIRTY_DAYS_AGO_DELTA
    monthly_contribution_proxy = Decimal(
        str(max(monthly_savings_brl, 0.0) / max(len(goals), 1))
    )

    # Batch-fetch recent contributions for all goals of this user (single query)
    recent_rows = (
        db.session.query(
            GoalContribution.goal_id,
            func.sum(GoalContribution.amount).label("total"),
        )
        .filter(
            GoalContribution.user_id == user_id,
            GoalContribution.created_at >= cutoff,
        )
        .group_by(GoalContribution.goal_id)
        .all()
    )
    recent_by_goal: dict[object, float] = {
        str(r.goal_id): float(r.total) for r in recent_rows
    }

    projection_service = GoalProjectionService(
        monthly_contribution=monthly_contribution_proxy
    )

    result: list[dict[str, Any]] = []
    for goal in goals:
        current = Decimal(str(goal.current_amount or 0))
        target = Decimal(str(goal.target_amount or 0))
        progress_pct = round(float(current / target * 100), 1) if target > 0 else 0.0

        projection = projection_service.project(
            goal_id=goal.id,
            user_id=user_id,
            current_amount=current,
            target_amount=target,
            target_date=goal.target_date,
        )

        days_remaining: int | None = None
        if goal.target_date:
            days_remaining = max((goal.target_date - today).days, 0)

        serialized = projection_service.serialize(projection)
        result.append(
            {
                "title": goal.title,
                "progress_pct": progress_pct,
                "current_amount": float(current),
                "target_amount": float(target),
                "target_date": goal.target_date.isoformat()
                if goal.target_date
                else None,
                "days_remaining": days_remaining,
                "recent_contributions_30d": recent_by_goal.get(str(goal.id), 0.0),
                "on_track": serialized["on_track"],
                "months_to_completion": serialized["months_to_completion"],
                "suggested_monthly_contribution": serialized[
                    "suggested_monthly_contribution"
                ],
            }
        )

    return result


def _build_overall_budget_snapshot(
    *,
    user_id: UUID,
    total_expense_brl: float,
) -> dict[str, Any] | None:
    """Return utilization of the overall monthly budget (tag_id IS NULL), or None.

    Category budgets linked via tag_id are excluded intentionally — tags are labels,
    not categories, so tag-based calculations risk misleading insights.
    """
    budget: Budget | None = (
        db.session.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.is_active.is_(True),
            Budget.tag_id.is_(None),
            Budget.period == "monthly",
        )
        .first()
    )
    if budget is None:
        return None

    budget_amount = float(budget.amount)
    utilization_pct = (
        round(total_expense_brl / budget_amount * 100, 1) if budget_amount > 0 else 0.0
    )
    return {
        "name": budget.name,
        "budget_amount": budget_amount,
        "spent": round(total_expense_brl, 2),
        "utilization_pct": utilization_pct,
        "exceeded": total_expense_brl > budget_amount,
    }


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_spending_prompt(
    snapshot: dict[str, Any],
    month_label: str,
    *,
    previous_insight: str | None = None,
    is_recap: bool = False,
    goals: list[dict[str, Any]] | None = None,
    budget: dict[str, Any] | None = None,
) -> str:
    context = json.dumps(snapshot, ensure_ascii=False, default=str)

    previous_block = ""
    if previous_insight:
        previous_block = (
            f"\nInsight do dia anterior (use para identificar o que mudou):\n"
            f"{previous_insight}\n"
        )

    goals_block = ""
    if goals:
        goals_json = json.dumps(goals, ensure_ascii=False, default=str)
        goals_block = f"\nMetas financeiras ativas do usuário:\n{goals_json}\n"

    budget_block = ""
    if budget:
        budget_json = json.dumps(budget, ensure_ascii=False, default=str)
        budget_block = f"\nOrçamento mensal geral configurado:\n{budget_json}\n"

    cross_domain_types = (
        "gasto_elevado, oportunidade_economia, saude_financeira, "
        "alerta_orcamento, padrao_gasto, alerta_meta, progresso_meta, "
        "orcamento_ultrapassado, planejamento_meta"
    )

    if is_recap:
        return (
            f"Você é um consultor financeiro pessoal. Hoje é o último dia de {month_label}. "  # noqa: E501
            "Faça uma análise completa: identifique padrões, conquistas e pontos de melhoria. "  # noqa: E501
            "Gere um recap em português brasileiro com: "
            "1) Resumo executivo do mês, "
            "2) Top 3 gastos do período, "
            "3) Comparação com o comportamento esperado, "
            "4) 3 direcionamentos práticos para o próximo mês.\n"
            f"{previous_block}"
            f"\nDados financeiros de {month_label}:\n{context}\n"
            f"{goals_block}"
            f"{budget_block}\n"
            f"Tipos de insight disponíveis: {cross_domain_types}.\n"
            "Se houver metas em risco ou orçamento próximo do limite, inclua insights "
            "dos tipos alerta_meta, progresso_meta, "
            "orcamento_ultrapassado ou planejamento_meta.\n\n"
            "Retorne um JSON array no formato:\n"
            '[{"type": "...", "title": "...", "message": "..."}]'
        )

    return (
        f"Você é um consultor financeiro pessoal. Analise os dados de gastos de {month_label} "  # noqa: E501
        "abaixo e gere 3 insights práticos e personalizados em português brasileiro. "
        f"Para cada insight, identifique o tipo ({cross_domain_types}), "
        "um título curto e uma recomendação específica e acionável.\n"
        f"{previous_block}"
        f"\nDados financeiros do período:\n{context}\n"
        f"{goals_block}"
        f"{budget_block}\n"
        "Ao identificar cruzamentos entre gastos e metas (ex: crescimento de gastos "
        "comprometendo prazo de uma meta), priorize insights dos tipos alerta_meta, "
        "progresso_meta ou planejamento_meta.\n\n"
        "Retorne um JSON array no formato:\n"
        '[{"type": "...", "title": "...", "message": "..."}]'
    )


def _build_goal_projection_prompt(
    *,
    goal_title: str,
    projection: dict[str, Any],
    user_context: str,
    monthly_contribution: Decimal,
) -> str:
    proj_json = json.dumps(projection, ensure_ascii=False, default=str)
    return (
        f"Você é um consultor financeiro pessoal. O usuário tem uma meta financeira "
        f"chamada '{goal_title}' e planeja contribuir R$ {monthly_contribution:.2f}/mês.\n\n"  # noqa: E501
        f"Contexto do usuário: {user_context}\n\n"
        f"Projeção matemática calculada:\n{proj_json}\n\n"
        "Com base nesses dados, gere uma narrativa motivacional e prática em português "
        "brasileiro (máximo 200 palavras) que:\n"
        "1. Explique claramente quando a meta será alcançada\n"
        "2. Diga se o usuário está no caminho certo ou precisa ajustar\n"
        "3. Ofereça 1-2 recomendações específicas e acionáveis\n"
        "4. Use tom encorajador mas realista\n\n"
        "Retorne apenas o texto da narrativa, sem JSON."
    )


def _build_weekly_summary_prompt(summary: Any) -> str:
    context = json.dumps(
        {
            "semana_atual": summary.get("current_week"),
            "semana_anterior": summary.get("previous_week"),
            "comparativo": summary.get("comparison"),
        },
        ensure_ascii=False,
        default=str,
    )
    return (
        "Você é um consultor financeiro pessoal. Analise o resumo financeiro semanal "
        "abaixo e gere um briefing conciso em português brasileiro (máximo 150 palavras) que:\n"  # noqa: E501
        "1. Destaque o desempenho desta semana vs. semana anterior\n"
        "2. Aponte o ponto mais crítico (gasto ou renda) que merece atenção\n"
        "3. Termine com uma dica prática para a próxima semana\n\n"
        f"Dados do resumo semanal:\n{context}\n\n"
        "Retorne apenas o texto do briefing, sem JSON."
    )


__all__ = [
    "AIAdvisoryService",
]
