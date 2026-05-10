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

from sqlalchemy import case, func

from app.extensions.database import db
from app.models.goal import Goal
from app.models.llm_audit_log import LLMAuditLog
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.goal_projection_service import GoalProjectionService
from app.services.llm_provider import LLMProvider, LLMProviderError, get_llm_provider
from app.services.weekly_summary import compute_weekly_summary

log = logging.getLogger(__name__)


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

        Args:
            month: "YYYY-MM" string. Defaults to the current calendar month.

        Returns:
            {"insights": str, "tokens_used": int, "cost_usd": float,
             "month": "YYYY-MM", "model": str}
        """
        today = date.today()
        if month:
            year, mon = int(month[:4]), int(month[5:7])
        else:
            year, mon = today.year, today.month

        start = date(year, mon, 1)
        end = date(year, mon, monthrange(year, mon)[1])

        snapshot = self._build_spending_snapshot(start=start, end=end)
        prompt = _build_spending_prompt(snapshot, month_label=f"{year}-{mon:02d}")

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

        return {
            "insights": llm_resp.content,
            "tokens_used": llm_resp.total_tokens,
            "cost_usd": llm_resp.estimated_cost_usd,
            "month": f"{year}-{mon:02d}",
            "model": llm_resp.model,
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
# Prompt builders
# ---------------------------------------------------------------------------


def _build_spending_prompt(snapshot: dict[str, Any], month_label: str) -> str:
    context = json.dumps(snapshot, ensure_ascii=False, default=str)
    return (
        f"Você é um consultor financeiro pessoal. Analise os dados de gastos de {month_label} "  # noqa: E501
        "abaixo e gere 3 insights práticos e personalizados em português brasileiro. "
        "Para cada insight, identifique o tipo (gasto_elevado, oportunidade_economia, "
        "saude_financeira, alerta_orcamento, padrao_gasto), um título curto e "
        "uma recomendação específica e acionável.\n\n"
        f"Dados financeiros do período:\n{context}\n\n"
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
