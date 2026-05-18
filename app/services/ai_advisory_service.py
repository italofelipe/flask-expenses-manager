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

import hashlib
import json
import logging
from calendar import monthrange
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from dateutil.relativedelta import relativedelta
from sqlalchemy import case, func

from app.extensions.database import db
from app.extensions.prometheus_metrics import record_ai_insight_generated
from app.models.ai_insight import AIInsight, InsightType
from app.models.budget import Budget
from app.models.goal import Goal
from app.models.goal_contribution import GoalContribution
from app.models.llm_audit_log import LLMAuditLog
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.ai_lgpd import (
    ensure_ai_consent_granted,
    minimize_prompt_data,
    minimize_text,
    redact_prompt_for_audit,
    redact_response_for_audit,
)
from app.services.financial_insight_context_builder import (
    INSIGHT_DIMENSIONS,
    FinancialInsightContextBuilder,
    truncate_snapshot,
)
from app.services.goal_projection_service import GoalProjectionService
from app.services.insight_evidence_validator import filter_valid_items
from app.services.llm_provider import LLMProvider, LLMProviderError, get_llm_provider
from app.services.weekly_summary import compute_weekly_summary

log = logging.getLogger(__name__)

_SPENDING_INSIGHT_TYPES = (
    "gasto_elevado",
    "oportunidade_economia",
    "saude_financeira",
    "alerta_orcamento",
    "padrao_gasto",
    "alerta_meta",
    "progresso_meta",
    "orcamento_ultrapassado",
    "planejamento_meta",
    "saude_orcamento_mensal",
    "conquista_meta",
    "savings_rate_gap",
)

_SPENDING_INSIGHTS_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "spending_insight_items",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": list(_SPENDING_INSIGHT_TYPES),
                        },
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                    },
                    "required": ["type", "title", "message"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["items"],
        "additionalProperties": False,
    },
}

_FINANCIAL_INSIGHT_RESPONSE_SCHEMA: dict[str, Any] = {
    "name": "financial_insight_response",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": list(_SPENDING_INSIGHT_TYPES),
                        },
                        "dimension": {
                            "type": "string",
                            "enum": list(INSIGHT_DIMENSIONS),
                        },
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                        "evidence": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                    },
                    "required": [
                        "type",
                        "dimension",
                        "title",
                        "message",
                        "evidence",
                    ],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["summary", "items"],
        "additionalProperties": False,
    },
}

InsightItem = dict[str, str]
FinancialInsightItem = dict[str, Any]


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
    insight: AIInsight | None = (
        db.session.query(AIInsight)
        .filter_by(
            user_id=user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        .first()
    )
    return insight


def _get_latest_insight(*, user_id: UUID) -> AIInsight | None:
    """Return the most recently created AIInsight for this user, or None."""
    insight: AIInsight | None = (
        db.session.query(AIInsight)
        .filter_by(user_id=user_id)
        .order_by(AIInsight.created_at.desc())
        .first()
    )
    return insight


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
    metadata: dict[str, Any] | None = None,
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
    if metadata:
        insight.metadata_dict = metadata
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


def _strip_json_code_fence(content: str) -> str:
    text = content.strip()
    if not text.startswith("```"):
        return text

    first_newline = text.find("\n")
    if first_newline == -1:
        return text

    text = text[first_newline + 1 :]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    return text.strip()


def _coerce_spending_insight_items(content: str) -> list[InsightItem]:
    raw = _strip_json_code_fence(content)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("Invalid spending insight JSON.") from exc

    candidate_items = parsed.get("items") if isinstance(parsed, dict) else parsed
    if not isinstance(candidate_items, list) or not candidate_items:
        raise LLMProviderError("Invalid spending insight items.")

    items: list[InsightItem] = []
    for candidate in candidate_items:
        if not isinstance(candidate, dict):
            raise LLMProviderError("Invalid spending insight item.")

        item_type = candidate.get("type")
        title = candidate.get("title")
        message = candidate.get("message")
        if (
            not isinstance(item_type, str)
            or not item_type.strip()
            or not isinstance(title, str)
            or not title.strip()
            or not isinstance(message, str)
            or not message.strip()
        ):
            raise LLMProviderError("Invalid spending insight item fields.")

        items.append(
            {
                "type": item_type.strip(),
                "title": title.strip(),
                "message": message.strip(),
            }
        )

    return items


def _coerce_financial_insight_item(candidate: object) -> FinancialInsightItem:
    if not isinstance(candidate, dict):
        raise LLMProviderError("Invalid financial insight item.")

    item_type = candidate.get("type")
    title = candidate.get("title")
    message = candidate.get("message")
    evidence = candidate.get("evidence")
    if (
        not isinstance(item_type, str)
        or item_type.strip() not in _SPENDING_INSIGHT_TYPES
        or not isinstance(title, str)
        or not title.strip()
        or not isinstance(message, str)
        or not message.strip()
        or not isinstance(evidence, list)
        or not evidence
        or not all(isinstance(item, str) and item.strip() for item in evidence)
    ):
        raise LLMProviderError("Invalid financial insight item fields.")

    # Dimension is required for new MVP-3 items; legacy AIInsight rows (pre
    # 2026-05-18) may not have it — those get coerced to 'general'. Invalid
    # explicit values are rejected so the schema stays a closed enum.
    dimension_raw = candidate.get("dimension")
    if dimension_raw is None:
        dimension = "general"
    elif isinstance(dimension_raw, str) and dimension_raw.strip() in INSIGHT_DIMENSIONS:
        dimension = dimension_raw.strip()
    else:
        raise LLMProviderError("Invalid financial insight item dimension.")

    return {
        "type": item_type.strip(),
        "dimension": dimension,
        "title": title.strip(),
        "message": message.strip(),
        "evidence": [item.strip() for item in evidence],
    }


def _coerce_financial_insight_metadata(parsed: dict[str, Any]) -> dict[str, str]:
    metadata: dict[str, str] = {}
    candidate_metadata = parsed.get("metadata")
    if not isinstance(candidate_metadata, dict):
        return metadata

    context_schema_version = candidate_metadata.get("context_schema_version")
    context_hash = candidate_metadata.get("context_hash")
    if isinstance(context_schema_version, str) and context_schema_version.strip():
        metadata["context_schema_version"] = context_schema_version.strip()
    if isinstance(context_hash, str) and context_hash.strip():
        metadata["context_hash"] = context_hash.strip()
    return metadata


def _coerce_financial_insight_response(
    content: str,
) -> tuple[str, list[FinancialInsightItem], dict[str, str]]:
    raw = _strip_json_code_fence(content)
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise LLMProviderError("Invalid financial insight JSON.") from exc

    if not isinstance(parsed, dict):
        raise LLMProviderError("Invalid financial insight response.")

    summary = parsed.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise LLMProviderError("Invalid financial insight summary.")

    candidate_items = parsed.get("items")
    if not isinstance(candidate_items, list) or not candidate_items:
        raise LLMProviderError("Invalid financial insight items.")

    items = [_coerce_financial_insight_item(item) for item in candidate_items]
    # Issue #1300: drop items whose evidence paths disagree with the declared
    # dimension (or point to unknown snapshot prefixes). Surviving items keep
    # their order. When every item is rejected, surface as a provider error.
    items = filter_valid_items(items)
    if not items:
        raise LLMProviderError(
            "All financial insight items rejected by evidence validation."
        )
    metadata = _coerce_financial_insight_metadata(parsed)

    return summary.strip(), items, metadata


def _serialize_spending_insight_items(items: list[InsightItem]) -> str:
    return json.dumps(items, ensure_ascii=False, separators=(",", ":"))


def _serialize_financial_insight_response(
    *,
    summary: str,
    items: list[FinancialInsightItem],
    metadata: dict[str, str] | None = None,
) -> str:
    payload: dict[str, Any] = {"summary": summary, "items": items}
    if metadata:
        payload["metadata"] = metadata
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def _financial_context_hash(snapshot: dict[str, Any]) -> str:
    serialized = json.dumps(
        snapshot,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _log_llm_call(
    *,
    user_id: UUID,
    endpoint: str,
    prompt: str,
    llm_response: Any,
    consent_version: str | None = None,
) -> None:
    """Persist an :class:`LLMAuditLog` row with redacted prompt/response.

    The ``prompt`` and ``response_text`` columns store hash markers (and a
    bounded, minimised preview for the response) — never the raw text. This
    keeps the audit trail forensically linkable without retaining PII (LGPD
    minimisation, issue #1258).

    Token counts, latency, cost, model and endpoint stay unredacted because
    they are non-PII operational signals required for cost tracking and
    rate-limit review.

    Failures here never break the advisory flow — the audit log is
    fire-and-forget by design.
    """
    try:
        log_row = LLMAuditLog(
            user_id=user_id,
            endpoint=endpoint,
            model=llm_response.model,
            prompt=redact_prompt_for_audit(prompt, consent_version=consent_version),
            response_text=redact_response_for_audit(llm_response.content),
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


def _build_period_snapshot(
    *,
    insight_type: InsightType,
    user_id: UUID,
    anchor: date,
    previous_generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Dispatch to the period-specific snapshot builder."""
    builder = FinancialInsightContextBuilder()
    if insight_type == InsightType.daily:
        return builder.build_daily(
            user_id=user_id,
            anchor_date=anchor,
            previous_generated_at=previous_generated_at,
        )
    if insight_type == InsightType.weekly:
        return builder.build_weekly(
            user_id=user_id,
            anchor_date=anchor,
            previous_generated_at=previous_generated_at,
        )
    if insight_type == InsightType.monthly:
        return builder.build_monthly(
            user_id=user_id,
            anchor_date=anchor,
            previous_generated_at=previous_generated_at,
        )
    raise ValueError("period_type must be daily, weekly or monthly")


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

    def generate_financial_insights(
        self,
        *,
        period_type: str,
        anchor_date: date | None = None,
    ) -> dict[str, Any]:
        """Generate period-aware financial insights with structured evidence."""
        normalized_period_type = period_type.strip().lower()
        insight_type = InsightType(normalized_period_type)
        anchor = anchor_date or date.today()
        consent_version = ensure_ai_consent_granted(self._user_id)

        previous = _get_latest_insight(user_id=self._user_id)
        snapshot = _build_period_snapshot(
            insight_type=insight_type,
            user_id=self._user_id,
            anchor=anchor,
            previous_generated_at=previous.created_at if previous else None,
        )

        period = snapshot["period"]
        period_label = str(period["label"])
        period_start = date.fromisoformat(str(period["start"]))
        period_end = date.fromisoformat(str(period["end"]))
        context_version = str(snapshot["schema_version"])

        cached = _get_cached_insight(
            user_id=self._user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        if cached is not None:
            try:
                (
                    cached_summary,
                    cached_items,
                    cached_metadata,
                ) = _coerce_financial_insight_response(cached.content)
            except LLMProviderError:
                log.warning(
                    "ai_advisory.financial_insights.cached_parse_failed "
                    "user=%s insight=%s",
                    self._user_id,
                    cached.id,
                )
            else:
                return {
                    "period_type": normalized_period_type,
                    "period_label": cached.period_label,
                    "period_start": cached.period_start.isoformat(),
                    "period_end": cached.period_end.isoformat(),
                    "summary": cached_summary,
                    "items": cached_items,
                    "context_version": cached_metadata.get(
                        "context_schema_version", context_version
                    ),
                    "context_hash": cached_metadata.get("context_hash"),
                    "tokens_used": cached.tokens_used,
                    "cost_usd": float(cached.cost_usd),
                    "model": cached.model,
                    "cached": True,
                }

        prompt_snapshot = minimize_prompt_data(snapshot)
        # Apply 12 KiB cap before hashing/prompting so context_hash matches
        # whatever we actually send to the LLM.
        prompt_snapshot, truncation_info = truncate_snapshot(prompt_snapshot)
        context_hash = _financial_context_hash(prompt_snapshot)
        prompt = _build_financial_insight_prompt(
            prompt_snapshot,
            period_type=normalized_period_type,
        )

        try:
            llm_resp = self._provider.generate_with_usage(
                prompt,
                response_schema=_FINANCIAL_INSIGHT_RESPONSE_SCHEMA,
            )
        except LLMProviderError as exc:
            log.warning(
                "ai_advisory.financial_insights.llm_error "
                "user=%s period_type=%s error=%s",
                self._user_id,
                normalized_period_type,
                exc,
            )
            raise

        summary, items, _ = _coerce_financial_insight_response(llm_resp.content)
        metadata = {
            "context_schema_version": context_version,
            "context_hash": context_hash,
        }
        serialized_content = _serialize_financial_insight_response(
            summary=summary,
            items=items,
            metadata=metadata,
        )

        _log_llm_call(
            user_id=self._user_id,
            endpoint=f"financial_insights_{normalized_period_type}",
            prompt=prompt,
            llm_response=llm_resp,
            consent_version=consent_version,
        )

        dimensions_present = sorted(
            {str(it.get("dimension", "general")) for it in items}
        )
        comparisons_available = sorted((snapshot.get("comparisons") or {}).keys())
        persist_metadata: dict[str, Any] = {
            "snapshot_version": context_version,
            "context_hash": context_hash,
            "comparisons_available": comparisons_available,
            "dimensions_present": dimensions_present,
            "snapshot_bytes_original": truncation_info["snapshot_bytes_original"],
            "snapshot_bytes_final": truncation_info["snapshot_bytes_final"],
            "truncated": bool(truncation_info["truncated"]),
        }
        if truncation_info["dropped_sections"]:
            persist_metadata["dropped_sections"] = list(
                truncation_info["dropped_sections"]
            )

        _save_insight(
            user_id=self._user_id,
            content=serialized_content,
            insight_type=insight_type,
            period_label=period_label,
            period_start=period_start,
            period_end=period_end,
            model=llm_resp.model,
            tokens_used=llm_resp.total_tokens,
            cost_usd=llm_resp.estimated_cost_usd,
            previous_insight_id=previous.id if previous else None,
            metadata=persist_metadata,
        )

        try:
            record_ai_insight_generated(
                period_type=normalized_period_type,
                dimensions=dimensions_present,
                tokens_used=int(llm_resp.total_tokens or 0),
                snapshot_bytes=int(truncation_info["snapshot_bytes_final"]),
                truncated=bool(truncation_info["truncated"]),
            )
        except Exception:  # pragma: no cover — metrics are fire-and-forget
            log.warning(
                "ai_advisory.metrics.record_failed user=%s period=%s",
                self._user_id,
                normalized_period_type,
            )

        return {
            "period_type": normalized_period_type,
            "period_label": period_label,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "summary": summary,
            "items": items,
            "context_version": context_version,
            "context_hash": context_hash,
            "tokens_used": llm_resp.total_tokens,
            "cost_usd": llm_resp.estimated_cost_usd,
            "model": llm_resp.model,
            "cached": False,
        }

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
            {"insights": str, "items": list[dict], "tokens_used": int,
             "cost_usd": float, "month": "YYYY-MM", "model": str, "cached": bool}

        Raises:
            AIConsentRequiredError: When the user has not granted (or has
                revoked) the ``AI`` LGPD consent (#1258).
        """
        consent_version = ensure_ai_consent_granted(self._user_id)
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

        # Idempotency: return cached insight if already generated today.
        # The consent gate above already ensured the user has an active
        # ``AI`` consent — replays are safe to serve from cache.
        cached = _get_cached_insight(
            user_id=self._user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        if cached is not None:
            cached_items: list[InsightItem] = []
            try:
                cached_items = _coerce_spending_insight_items(cached.content)
            except LLMProviderError:
                log.warning(
                    "ai_advisory.spending_insights.cached_parse_failed "
                    "user=%s insight=%s",
                    self._user_id,
                    cached.id,
                )
            return {
                "insights": cached.content,
                "items": cached_items,
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

        monthly_budget_by_category: list[dict[str, Any]] = []
        monthly_goals_evolution: list[dict[str, Any]] = []
        savings_rate_ctx: dict[str, Any] | None = None

        if is_recap:
            monthly_budget_by_category = _build_monthly_budget_by_category(
                user_id=self._user_id,
                period_start=start,
                period_end=end,
            )
            monthly_goals_evolution = _build_monthly_goals_evolution(
                user_id=self._user_id,
                period_start=start,
                period_end=end,
            )
            # Pull user monthly_income for savings rate benchmark
            from app.models.user import User

            user_row = db.session.query(User).filter_by(id=self._user_id).first()
            monthly_income = float(user_row.monthly_income or 0) if user_row else 0.0
            savings_rate_ctx = _build_savings_rate_context(
                monthly_income=monthly_income,
                total_income=snapshot["total_income"],
                balance=snapshot["balance"],
            )

        prompt = _build_spending_prompt(
            minimize_prompt_data(snapshot),
            month_label=f"{year}-{mon:02d}",
            previous_insight=previous_content,
            is_recap=is_recap,
            goals=goals_ctx,
            budget=budget_ctx,
            monthly_budget_by_category=monthly_budget_by_category,
            monthly_goals_evolution=monthly_goals_evolution,
            savings_rate_ctx=savings_rate_ctx,
        )

        try:
            llm_resp = self._provider.generate_with_usage(
                prompt,
                response_schema=_SPENDING_INSIGHTS_RESPONSE_SCHEMA,
            )
        except LLMProviderError as exc:
            log.warning(
                "ai_advisory.spending_insights.llm_error user=%s error=%s",
                self._user_id,
                exc,
            )
            raise

        insight_items = _coerce_spending_insight_items(llm_resp.content)
        serialized_insights = _serialize_spending_insight_items(insight_items)

        _log_llm_call(
            user_id=self._user_id,
            endpoint="spending_insights",
            prompt=prompt,
            llm_response=llm_resp,
            consent_version=consent_version,
        )

        # AIInsight does not yet carry a dedicated ``consent_version_id``
        # column (follow-up issue tracked in the PR description). The same
        # value is preserved on the ``LLMAuditLog`` row above so the LGPD
        # audit chain stays complete — see ``docs/lgpd/AI_MINIMIZATION.md``.
        _save_insight(
            user_id=self._user_id,
            content=serialized_insights,
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
            "insights": serialized_insights,
            "items": insight_items,
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

        pending_expense_rows = (
            db.session.query(
                Transaction.description.label("description"),
                func.sum(Transaction.amount).label("total"),
            )
            .filter(
                Transaction.user_id == self._user_id,
                Transaction.deleted.is_(False),
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == TransactionStatus.PENDING,
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
        pending_expenses = [
            {
                "description": r.description or "Sem descrição",
                "total": _safe_float(r.total),
            }
            for r in pending_expense_rows
        ]

        total_expense = _safe_float(row.total_expense)
        total_income = _safe_float(row.total_income)
        pending_expense_total = round(
            sum(float(item["total"]) for item in pending_expenses),
            2,
        )
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
            "pending_expense_total": pending_expense_total,
            "balance": balance,
            "savings_rate_pct": savings_rate,
            "transaction_count": int(row.tx_count or 0),
            "top_expenses": top_expenses,
            "pending_expenses": pending_expenses,
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
            AIConsentRequiredError: When the user has not granted the ``AI``
                LGPD consent (#1258).
        """
        consent_version = ensure_ai_consent_granted(self._user_id)
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
            goal_title=minimize_text(str(goal.title)) or "meta",
            projection=projection_data,
            user_context=minimize_text(user_context),
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
            consent_version=consent_version,
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
            AIConsentRequiredError: When the user has not granted the ``AI``
                LGPD consent (#1258).
        """
        consent_version = ensure_ai_consent_granted(self._user_id)
        today = date.today()
        week_start = today - relativedelta(days=today.weekday())
        week_end = week_start + relativedelta(days=6)

        summary = compute_weekly_summary(user_id=self._user_id)
        top_categories = _build_weekly_top_categories(
            user_id=self._user_id, week_start=week_start, week_end=week_end
        )
        budget_snapshot = _build_weekly_budget_snapshot(
            user_id=self._user_id, week_start=week_start, week_end=week_end
        )
        goals_snapshot = _build_weekly_goals_snapshot(
            user_id=self._user_id, week_start=week_start, week_end=week_end
        )
        prompt = _build_weekly_summary_prompt(
            summary,
            top_categories=top_categories,
            budget_snapshot=budget_snapshot,
            goals_snapshot=goals_snapshot,
        )

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
            consent_version=consent_version,
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
# Weekly-specific helpers
# ---------------------------------------------------------------------------


def _build_weekly_top_categories(
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
    top_n: int = 3,
) -> list[dict[str, Any]]:
    """Return top N expense categories by spend in the given week.

    Only transactions with category IS NOT NULL are counted.
    """

    rows = (
        db.session.query(
            Transaction.category.label("category"),
            func.sum(Transaction.amount).label("total"),
        )
        .filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.status == TransactionStatus.PAID,
            Transaction.deleted.is_(False),
            Transaction.category.isnot(None),
            Transaction.due_date >= week_start,
            Transaction.due_date <= week_end,
        )
        .group_by(Transaction.category)
        .order_by(func.sum(Transaction.amount).desc())
        .limit(top_n)
        .all()
    )

    total_spent = sum(float(r.total or 0) for r in rows) or 1.0
    return [
        {
            "category": r.category.value
            if hasattr(r.category, "value")
            else str(r.category),
            "total": round(float(r.total or 0), 2),
            "pct_of_total": round(float(r.total or 0) / total_spent * 100, 1),
        }
        for r in rows
    ]


def _build_weekly_budget_snapshot(
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[dict[str, Any]]:
    """Return pro-rata utilization per active category budget for the current week."""
    from calendar import monthrange

    budgets = (
        db.session.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.is_active.is_(True),
            Budget.category.isnot(None),
            Budget.period == "monthly",
        )
        .all()
    )
    if not budgets:
        return []

    today = date.today()
    days_in_month = monthrange(today.year, today.month)[1]
    # Days elapsed in month up to end of week (capped at month end)
    days_elapsed = min(
        (week_end - date(today.year, today.month, 1)).days + 1, days_in_month
    )

    result: list[dict[str, Any]] = []
    for budget in budgets:
        budget_amount = float(budget.amount)
        prorated_limit = round(budget_amount * days_elapsed / days_in_month, 2)

        # Spending for this category this week
        spent_row = db.session.query(
            func.coalesce(func.sum(Transaction.amount), 0)
        ).filter(
            Transaction.user_id == user_id,
            Transaction.type == TransactionType.EXPENSE,
            Transaction.status == TransactionStatus.PAID,
            Transaction.deleted.is_(False),
            Transaction.due_date >= week_start,
            Transaction.due_date <= week_end,
        )
        from app.models.transaction import TransactionCategory

        try:
            cat_enum = TransactionCategory(budget.category)
            spent_row = spent_row.filter(Transaction.category == cat_enum)
        except ValueError:
            continue

        weekly_spent = round(float(spent_row.scalar() or 0), 2)

        if weekly_spent > prorated_limit:
            pace = "exceeded"
        elif prorated_limit > 0 and weekly_spent / prorated_limit >= 0.8:
            pace = "alert"
        else:
            pace = "ok"

        result.append(
            {
                "category": budget.category,
                "monthly_budget": budget_amount,
                "weekly_spent": weekly_spent,
                "prorated_limit": prorated_limit,
                "pace_status": pace,
            }
        )

    return result


def _build_weekly_goals_snapshot(
    *,
    user_id: UUID,
    week_start: date,
    week_end: date,
) -> list[dict[str, Any]]:
    """Return active goals with their contribution amount this week."""
    goals = (
        db.session.query(Goal)
        .filter_by(user_id=user_id, status="active")
        .order_by(Goal.priority, Goal.created_at)
        .all()
    )
    if not goals:
        return []

    # Batch-fetch weekly contributions
    from datetime import datetime

    week_start_dt = datetime(week_start.year, week_start.month, week_start.day)
    week_end_dt = datetime(week_end.year, week_end.month, week_end.day, 23, 59, 59)
    contrib_rows = (
        db.session.query(
            GoalContribution.goal_id,
            func.sum(GoalContribution.amount).label("total"),
        )
        .filter(
            GoalContribution.user_id == user_id,
            GoalContribution.created_at >= week_start_dt,
            GoalContribution.created_at <= week_end_dt,
        )
        .group_by(GoalContribution.goal_id)
        .all()
    )
    weekly_by_goal = {str(r.goal_id): float(r.total or 0) for r in contrib_rows}

    return [
        {
            "title": goal.title,
            "progress_pct": round(
                float(goal.current_amount or 0) / float(goal.target_amount) * 100, 1
            )
            if goal.target_amount
            else 0.0,
            "weekly_contribution": weekly_by_goal.get(str(goal.id), 0.0),
        }
        for goal in goals
    ]


# ---------------------------------------------------------------------------
# Recap-specific helpers
# ---------------------------------------------------------------------------


def _build_monthly_goals_evolution(
    *,
    user_id: UUID,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """Return active goals with total contributions made during the period."""
    from datetime import datetime

    goals = (
        db.session.query(Goal)
        .filter_by(user_id=user_id, status="active")
        .order_by(Goal.priority, Goal.created_at)
        .all()
    )
    if not goals:
        return []

    start_dt = datetime(period_start.year, period_start.month, period_start.day)
    end_dt = datetime(period_end.year, period_end.month, period_end.day, 23, 59, 59)

    contrib_rows = (
        db.session.query(
            GoalContribution.goal_id,
            func.sum(GoalContribution.amount).label("total"),
        )
        .filter(
            GoalContribution.user_id == user_id,
            GoalContribution.created_at >= start_dt,
            GoalContribution.created_at <= end_dt,
        )
        .group_by(GoalContribution.goal_id)
        .all()
    )
    monthly_by_goal = {str(r.goal_id): float(r.total or 0) for r in contrib_rows}

    return [
        {
            "title": goal.title,
            "progress_pct": round(
                float(goal.current_amount or 0) / float(goal.target_amount) * 100, 1
            )
            if goal.target_amount
            else 0.0,
            "monthly_contributions": monthly_by_goal.get(str(goal.id), 0.0),
            "target_date": goal.target_date.isoformat() if goal.target_date else None,
        }
        for goal in goals
    ]


def _build_savings_rate_context(
    *,
    monthly_income: float,
    total_income: float,
    balance: float,
) -> dict[str, Any] | None:
    """Return savings rate vs 20% benchmark. Returns None if no income data."""
    income = total_income or monthly_income
    if income <= 0:
        return None

    actual_rate = round(balance / income * 100, 1)
    benchmark = 20.0
    gap = round(actual_rate - benchmark, 1)
    return {
        "actual_rate_pct": actual_rate,
        "benchmark_pct": benchmark,
        "gap_pct": gap,
        "assessment": "above" if actual_rate >= benchmark else "below",
    }


def _build_monthly_budget_by_category(
    *,
    user_id: UUID,
    period_start: date,
    period_end: date,
) -> list[dict[str, Any]]:
    """Return budget utilization per category for the given period."""
    budgets = (
        db.session.query(Budget)
        .filter(
            Budget.user_id == user_id,
            Budget.is_active.is_(True),
            Budget.category.isnot(None),
        )
        .all()
    )
    if not budgets:
        return []

    from app.models.transaction import TransactionCategory

    result: list[dict[str, Any]] = []
    for budget in budgets:
        try:
            cat_enum = TransactionCategory(budget.category)
        except ValueError:
            continue

        spent_val = (
            db.session.query(func.coalesce(func.sum(Transaction.amount), 0))
            .filter(
                Transaction.user_id == user_id,
                Transaction.type == TransactionType.EXPENSE,
                Transaction.status == TransactionStatus.PAID,
                Transaction.deleted.is_(False),
                Transaction.category == cat_enum,
                Transaction.due_date >= period_start,
                Transaction.due_date <= period_end,
            )
            .scalar()
        )

        budget_amount = float(budget.amount)
        spent = round(float(spent_val or 0), 2)
        utilization = (
            round(spent / budget_amount * 100, 1) if budget_amount > 0 else 0.0
        )

        result.append(
            {
                "category": budget.category,
                "budget_amount": budget_amount,
                "spent": spent,
                "utilization_pct": utilization,
                "exceeded": spent > budget_amount,
            }
        )

    return result


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_financial_insight_prompt(
    snapshot: dict[str, Any],
    *,
    period_type: str,
) -> str:
    context = json.dumps(snapshot, ensure_ascii=False, default=str)
    period_instruction = {
        "daily": (
            "Para insight diário: compare hoje com ontem, com o mesmo dia do mês "
            "passado quando disponível, recapitule rapidamente o mês até agora e "
            "resuma como o usuário está hoje."
        ),
        "weekly": (
            "Para insight semanal: resuma a semana, cite maiores e menores gastos, "
            "maiores e menores recebimentos, e identifique dias da semana com mais "
            "e menos consumo/recebimento quando os dados permitirem."
        ),
        "monthly": (
            "Para insight mensal: mostre o dia de maior gasto, maior recebimento, "
            "menor gasto com atividade, menor recebimento com atividade e faça um "
            "panorama geral do mês."
        ),
    }[period_type]

    insight_types = ", ".join(_SPENDING_INSIGHT_TYPES)
    return (
        "Você é um analista financeiro pessoal. Analise exclusivamente o snapshot "
        "financeiro estruturado abaixo e gere insights em português brasileiro, "
        "objetivos, personalizados e acionáveis.\n"
        f"{period_instruction}\n"
        "Use somente os dados do snapshot fornecido. Não invente transações, metas, "
        "orçamentos, rendas, despesas, nomes, datas ou valores ausentes. Quando uma "
        "comparação não existir, mencione a ausência apenas se ela for relevante.\n"
        "Cada item deve conter evidências que apontem para chaves conhecidas do "
        "snapshot, como current_period.paid.balance, comparisons.yesterday.delta, "
        "daily_series, extremes, categories, transactions.sample, budgets, goals, "
        "credit_cards ou wallet.\n"
        "Quando 'wallet' estiver presente e o ativo total for > 0, contextualize "
        "a rentabilidade e a alocação atual: compare com "
        "'wallet.benchmark.cdi_monthly_pct' e 'wallet.benchmark.ipca_monthly_pct' "
        "quando disponíveis, e sinalize desvios do perfil de investidor via "
        "'wallet.profile_alignment'. Quando o usuário não tiver perfil declarado, "
        "descreva a distribuição sem afirmações de adequação.\n"
        "Para mudanças desde a última geração, use somente "
        "transactions.changes_since_last_generation. Não use texto de insights "
        "anteriores como fonte factual.\n"
        f"\nSnapshot financeiro ({snapshot.get('schema_version')}):\n{context}\n\n"
        f"Tipos permitidos: {insight_types}.\n"
        "Retorne somente JSON no formato:\n"
        '{"summary":"...","items":[{"type":"saude_financeira",'
        '"dimension":"general","title":"...","message":"...",'
        '"evidence":["current_period.paid.balance"]}]}'
    )


def _build_spending_prompt(
    snapshot: dict[str, Any],
    month_label: str,
    *,
    previous_insight: str | None = None,
    is_recap: bool = False,
    goals: list[dict[str, Any]] | None = None,
    budget: dict[str, Any] | None = None,
    monthly_budget_by_category: list[dict[str, Any]] | None = None,
    monthly_goals_evolution: list[dict[str, Any]] | None = None,
    savings_rate_ctx: dict[str, Any] | None = None,
) -> str:
    context = json.dumps(snapshot, ensure_ascii=False, default=str)

    previous_block = ""
    if previous_insight:
        previous_block = (
            f"\nInsight do dia anterior (use para identificar o que mudou):\n"
            f"{previous_insight}\n"
        )

    goals_block = ""
    if goals is not None and len(goals) > 0:
        goals_json = json.dumps(goals, ensure_ascii=False, default=str)
        goals_block = f"\nMetas financeiras ativas do usuário:\n{goals_json}\n"
    elif goals is not None:
        goals_block = (
            "\nMetas financeiras ativas do usuário: Nenhuma meta financeira ativa "
            "cadastrada. Não invente metas e não trate orçamento como meta.\n"
        )

    budget_block = ""
    if budget:
        budget_json = json.dumps(budget, ensure_ascii=False, default=str)
        budget_block = f"\nOrçamento mensal geral configurado:\n{budget_json}\n"

    cross_domain_types = (
        "gasto_elevado, oportunidade_economia, saude_financeira, "
        "alerta_orcamento, padrao_gasto, alerta_meta, progresso_meta, "
        "orcamento_ultrapassado, planejamento_meta"
    )

    # Extra recap sections
    budget_by_cat_block = ""
    if monthly_budget_by_category:
        budget_by_cat_block = (
            "\nUtilização de orçamentos por categoria no mês:\n"
            + json.dumps(monthly_budget_by_category, ensure_ascii=False, default=str)
            + "\n"
        )

    goals_ev_block = ""
    if monthly_goals_evolution:
        goals_ev_block = (
            "\nEvolução de metas no mês (aportes realizados):\n"
            + json.dumps(monthly_goals_evolution, ensure_ascii=False, default=str)
            + "\n"
        )

    savings_rate_block = ""
    if savings_rate_ctx:
        savings_rate_block = (
            "\nTaxa de poupança do mês vs benchmark (20%):\n"
            + json.dumps(savings_rate_ctx, ensure_ascii=False, default=str)
            + "\n"
        )

    recap_types = (
        cross_domain_types
        + ", saude_orcamento_mensal, conquista_meta, savings_rate_gap"
    )

    if is_recap:
        return (
            f"Você é um consultor financeiro pessoal. Hoje é o último dia de {month_label}. "  # noqa: E501
            "Faça uma análise completa: identifique padrões, conquistas e pontos de melhoria. "  # noqa: E501
            "Gere um recap em português brasileiro com: "
            "1) Resumo executivo do mês, "
            "2) Top 3 gastos do período, "
            "3) Saúde dos orçamentos por categoria, "
            "4) Progresso nas metas, "
            "5) Taxa de poupança vs meta, "
            "6) 3 direcionamentos práticos para o próximo mês.\n"
            f"{previous_block}"
            f"\nDados financeiros de {month_label}:\n{context}\n"
            f"{goals_block}"
            f"{budget_block}"
            f"{budget_by_cat_block}"
            f"{goals_ev_block}"
            f"{savings_rate_block}\n"
            f"Tipos de insight disponíveis: {recap_types}.\n"
            "Inclua insights dos tipos saude_orcamento_mensal, conquista_meta e "
            "savings_rate_gap quando relevantes.\n\n"
            "Retorne um JSON array no formato:\n"
            '[{"type": "...", "title": "...", "message": "..."}]'
        )

    return (
        f"Você é um consultor financeiro pessoal. Analise os dados de gastos de {month_label} "  # noqa: E501
        "abaixo e gere 3 insights detalhados, práticos e personalizados em "
        "português brasileiro. "
        f"Para cada insight, identifique o tipo ({cross_domain_types}), "
        "um título curto e uma mensagem com: evidência numérica dos dados, "
        "interpretação financeira e uma próxima ação específica.\n"
        f"{previous_block}"
        f"\nDados financeiros do período:\n{context}\n"
        f"{goals_block}"
        f"{budget_block}\n"
        "Despesas com status pending são compromissos futuros; não trate como gasto "
        "já realizado.\n"
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


def _build_weekly_summary_prompt(
    summary: Any,
    *,
    top_categories: list[dict[str, Any]] | None = None,
    budget_snapshot: list[dict[str, Any]] | None = None,
    goals_snapshot: list[dict[str, Any]] | None = None,
) -> str:
    context = json.dumps(
        {
            "semana_atual": summary.get("current_week"),
            "semana_anterior": summary.get("previous_week"),
            "comparativo": summary.get("comparison"),
        },
        ensure_ascii=False,
        default=str,
    )

    top_cats_block = ""
    if top_categories:
        top_cats_block = (
            "\nTop categorias desta semana:\n"
            + json.dumps(top_categories, ensure_ascii=False, default=str)
            + "\n"
        )

    budget_block = ""
    if budget_snapshot:
        budget_block = (
            "\nRitmo de orçamentos por categoria (pro-rata semanal):\n"
            + json.dumps(budget_snapshot, ensure_ascii=False, default=str)
            + "\n"
        )

    goals_block = ""
    if goals_snapshot:
        goals_block = (
            "\nAportes em metas esta semana:\n"
            + json.dumps(goals_snapshot, ensure_ascii=False, default=str)
            + "\n"
        )

    return (
        "Você é um consultor financeiro pessoal. Analise o resumo financeiro semanal "
        "abaixo e gere um briefing conciso em português brasileiro (máximo 200 palavras) que:\n"  # noqa: E501
        "1. Destaque o desempenho desta semana vs. semana anterior\n"
        "2. Aponte o ponto mais crítico (gasto ou renda) que merece atenção\n"
        "3. Comente sobre categorias de alto gasto e ritmo de orçamentos\n"
        "4. Mencione aportes em metas se houver\n"
        "5. Termine com uma dica prática para a próxima semana\n\n"
        f"Dados do resumo semanal:\n{context}\n"
        f"{top_cats_block}"
        f"{budget_block}"
        f"{goals_block}\n"
        "Retorne apenas o texto do briefing, sem JSON."
    )


__all__ = [
    "AIAdvisoryService",
]
