"""AI Advisory Engine — generates personalised financial insights.

Usage:
    service = AdvisoryService(user_id=uid)
    result = service.get_insights()

The service gathers a financial snapshot, builds a prompt, calls the
configured LLM provider, and returns structured insights.
Insights are cached for 24 h and rate-limited to 5 calls/day per user.
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from typing import Any, TypedDict
from uuid import UUID

from sqlalchemy import case, func

from app.extensions.database import db
from app.models.goal import Goal
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.wallet import Wallet
from app.services.cache_service import get_cache_service
from app.services.llm_provider import LLMProvider, LLMProviderError, get_llm_provider

log = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 86_400  # 24 h
_RATE_LIMIT_CALLS = 5
_RATE_LIMIT_WINDOW_SECONDS = 86_400  # 24 h


class AdvisoryInsight(TypedDict):
    type: str
    title: str
    message: str


class AdvisoryResult(TypedDict):
    insights: list[AdvisoryInsight]
    generated_at: str
    source: str  # "llm" | "stub" | "cache"
    calls_remaining_today: int


class AdvisoryRateLimitError(Exception):
    """Raised when the user has exceeded the daily advisory rate limit."""


class AdvisoryService:
    def __init__(
        self,
        user_id: UUID,
        *,
        provider: LLMProvider | None = None,
    ) -> None:
        self._user_id = user_id
        self._provider = provider or get_llm_provider()
        self._cache = get_cache_service()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_insights(self) -> AdvisoryResult:
        """Return insights for this user, respecting cache and rate limit."""
        cache_key = f"advisory:insights:{self._user_id}"
        rate_key = f"advisory:rate:{self._user_id}"

        # Check cache first
        cached: AdvisoryResult | None = self._cache.get(cache_key)
        if cached is not None:
            calls_used = int(self._cache.get(rate_key) or 0)
            cached["calls_remaining_today"] = max(0, _RATE_LIMIT_CALLS - calls_used)
            cached["source"] = "cache"
            return cached

        # Rate limit check
        calls_used = int(self._cache.get(rate_key) or 0)
        if calls_used >= _RATE_LIMIT_CALLS:
            raise AdvisoryRateLimitError(
                f"Limite de {_RATE_LIMIT_CALLS} chamadas de advisory por dia atingido."
            )

        # Generate insights
        snapshot = self._build_snapshot()
        prompt = _build_prompt(snapshot)

        source = "llm"
        try:
            raw_text = self._provider.generate(prompt)
        except LLMProviderError as exc:
            log.warning("advisory.llm_error user=%s error=%s", self._user_id, exc)
            raw_text = StubFallback.generate(snapshot)
            source = "stub"

        insights = _parse_insights(raw_text)
        today_str = date.today().isoformat()
        result: AdvisoryResult = {
            "insights": insights,
            "generated_at": today_str,
            "source": source,
            "calls_remaining_today": _RATE_LIMIT_CALLS - calls_used - 1,
        }

        # Persist cache + increment rate counter
        self._cache.set(cache_key, result, ttl=_CACHE_TTL_SECONDS)
        new_count = calls_used + 1
        self._cache.set(rate_key, new_count, ttl=_RATE_LIMIT_WINDOW_SECONDS)

        return result

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_snapshot(self) -> dict[str, Any]:
        """Gather financial snapshot for the user (no PII)."""
        today = date.today()
        three_months_ago = today - timedelta(days=90)

        # Expense / income totals over the last 3 months
        agg = (
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
                ).label("expenses"),
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
                ).label("income"),
                func.count(Transaction.id).label("tx_count"),
            )
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.status == TransactionStatus.PAID,
                Transaction.due_date >= three_months_ago,
                Transaction.due_date <= today,
            )
            .one()
        )

        # Pending expenses (future obligations)
        pending_total = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == TransactionStatus.PENDING,
                Transaction.due_date >= today,
            )
            .scalar()
        )

        # Total assets from wallet
        assets = (
            db.session.query(func.coalesce(func.sum(Wallet.value), 0))
            .filter(
                Wallet.user_id == self._user_id,
                Wallet.should_be_on_wallet.is_(True),
                Wallet.value.isnot(None),
            )
            .scalar()
        )

        # Active goals (Goal has no deleted column)
        active_goals = Goal.query.filter_by(
            user_id=self._user_id, status="active"
        ).all()
        goals_summary = [
            {
                "title": g.title,
                "target_amount": float(g.target_amount or 0),
                "current_amount": float(g.current_amount or 0),
                "progress_pct": round(
                    float(g.current_amount or 0)
                    / max(float(g.target_amount or 1), 1)
                    * 100,
                    1,
                ),
            }
            for g in active_goals[:5]  # max 5 to keep prompt size small
        ]

        total_expense = float(agg.expenses or 0)
        total_income = float(agg.income or 0)
        avg_monthly_expense = round(total_expense / 3, 2)
        avg_monthly_income = round(total_income / 3, 2)
        total_assets = float(assets or 0)
        savings_rate = (
            round(
                (avg_monthly_income - avg_monthly_expense) / avg_monthly_income * 100, 1
            )
            if avg_monthly_income > 0
            else 0.0
        )

        return {
            "avg_monthly_expense": avg_monthly_expense,
            "avg_monthly_income": avg_monthly_income,
            "savings_rate_pct": savings_rate,
            "pending_obligations": float(pending_total or 0),
            "total_assets": total_assets,
            "survival_months": round(total_assets / avg_monthly_expense, 1)
            if avg_monthly_expense > 0
            else None,
            "active_goals": goals_summary,
            "tx_count_3m": int(agg.tx_count or 0),
        }


class StubFallback:
    """Generates rule-based insights when the LLM is unavailable."""

    @staticmethod
    def generate(snapshot: dict[str, Any]) -> str:
        insights = []
        avg_exp = float(snapshot.get("avg_monthly_expense") or 0)
        avg_inc = float(snapshot.get("avg_monthly_income") or 0)
        savings = float(snapshot.get("savings_rate_pct") or 0)
        survival = snapshot.get("survival_months")
        goals = snapshot.get("active_goals") or []

        if avg_inc > 0 and savings < 10:
            insights.append(
                "1. [gasto_elevado] Sua taxa de poupança está abaixo de 10%. "
                "Tente reduzir gastos variáveis em pelo menos R$ "
                f"{round(avg_exp * 0.05, 2)}/mês."
            )
        if survival is not None and float(survival) < 3:
            insights.append(
                "2. [reserva_critica] Sua reserva de emergência cobre menos de 3 meses. "  # noqa: E501
                "Priorize construir um colchão financeiro antes de outros objetivos."
            )
        for g in goals:
            if isinstance(g, dict) and float(g.get("progress_pct") or 0) < 30:
                insights.append(
                    f"3. [meta_em_risco] A meta '{g.get('title')}' está em "
                    f"{g.get('progress_pct')}% — considere aumentar aportes mensais."
                )
                break
        if not insights:
            insights.append(
                "1. [saude_financeira] Suas finanças estão equilibradas. "
                "Continue monitorando suas metas e considere aumentar aportes em investimentos."  # noqa: E501
            )
        return "\n".join(insights)


def _build_prompt(snapshot: dict[str, Any]) -> str:
    context = json.dumps(snapshot, ensure_ascii=False, default=str)
    types = "gasto_elevado, meta_em_risco, oportunidade_economia, reserva_critica, saude_financeira"  # noqa: E501
    return (
        "Você é um consultor financeiro pessoal. Analise os dados financeiros abaixo "
        "(sem PII) e gere exatamente 3 insights práticos "
        "em português brasileiro. Para cada insight: identifique o tipo "
        f"({types}), "
        "um título curto e uma mensagem clara com recomendação específica.\n\n"
        f"Dados financeiros:\n{context}\n\n"
        "Retorne um JSON array no formato:\n"
        '[{"type": "...", "title": "...", "message": "..."}, ...]'
    )


def _parse_insights(raw: str) -> list[AdvisoryInsight]:
    """Try to parse JSON from the LLM response; fall back to a single text insight."""
    import re

    # Extract JSON array from anywhere in the response
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        try:
            parsed = json.loads(match.group())
            if isinstance(parsed, list):
                return [
                    AdvisoryInsight(
                        type=str(item.get("type", "insight")),
                        title=str(item.get("title", "Insight")),
                        message=str(item.get("message", "")),
                    )
                    for item in parsed
                    if isinstance(item, dict)
                ]
        except (json.JSONDecodeError, KeyError):
            pass

    # Fallback: wrap raw text as a single insight
    return [
        AdvisoryInsight(
            type="insight",
            title="Análise financeira",
            message=raw.strip(),
        )
    ]


__all__ = [
    "AdvisoryInsight",
    "AdvisoryRateLimitError",
    "AdvisoryResult",
    "AdvisoryService",
]
