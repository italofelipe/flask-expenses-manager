"""Backend-only audit helpers for AI Insight preview and dossier export."""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from uuid import UUID

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
from app.models.user import User
from app.services.ai_advisory_service import (
    _build_period_snapshot,
    _financial_context_hash,
    _get_latest_insight,
)
from app.services.ai_insight_runs import create_ai_insight_run
from app.services.ai_lgpd import minimize_prompt_data
from app.services.financial_insight_context_builder import truncate_snapshot

PROMPT_TEMPLATE_VERSION = "financial-insight.v1.preview"
EVIDENCE_MANIFEST_VERSION = "ai_insight_evidence_manifest.v1"

_ALLOWED_PREVIEW_PERIODS = {
    InsightType.daily,
    InsightType.weekly,
    InsightType.monthly,
}


def _normalize_insight_type(period_type: str) -> InsightType:
    try:
        insight_type = InsightType(period_type.strip().lower())
    except (AttributeError, ValueError) as exc:
        raise ValueError("period_type deve ser daily, weekly ou monthly") from exc
    if insight_type not in _ALLOWED_PREVIEW_PERIODS:
        raise ValueError("period_type deve ser daily, weekly ou monthly")
    return insight_type


def _date_iso(value: object) -> str | None:
    return value.isoformat() if hasattr(value, "isoformat") else None


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def _json_safe_dict(value: dict[str, Any]) -> dict[str, Any]:
    decoded = _json_safe(value)
    return decoded if isinstance(decoded, dict) else {}


def _get_path(payload: dict[str, Any], path: str) -> Any:
    node: Any = payload
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def _safe_float(value: object) -> float:
    try:
        return float(value or 0)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0.0


def _financial_health_risk_flags(
    snapshot: dict[str, Any],
) -> list[dict[str, Any]] | None:
    financial_health = snapshot.get("financial_health")
    if not isinstance(financial_health, dict):
        return None
    risk_flags = financial_health.get("risk_flags")
    if not isinstance(risk_flags, list):
        return None
    return [flag for flag in risk_flags if isinstance(flag, dict)]


def _latest_snapshot_hash(
    *,
    user_id: UUID,
    period_type: InsightType,
) -> str | None:
    previous_run = (
        AIInsightRun.query.filter_by(user_id=user_id, period_type=period_type)
        .order_by(AIInsightRun.created_at.desc())
        .first()
    )
    return str(previous_run.snapshot_hash) if previous_run else None


def _evidence_item(
    *,
    snapshot: dict[str, Any],
    path: str,
    label: str,
    dimension: str,
) -> dict[str, Any] | None:
    value = _get_path(snapshot, path)
    if value is None:
        return None
    return {
        "path": path,
        "label": label,
        "dimension": dimension,
        "value": value,
    }


def build_evidence_manifest(
    *,
    snapshot: dict[str, Any],
    snapshot_hash: str,
) -> dict[str, Any]:
    """Return deterministic evidence pointers for an auditable snapshot."""

    evidence_paths = (
        (
            "financial_health.score",
            "Score determinístico de saúde financeira",
            "general",
        ),
        (
            "financial_health.risk_flags",
            "Flags determinísticas de risco",
            "general",
        ),
        (
            "current_period.paid.income_total",
            "Receitas pagas no período",
            "transactions",
        ),
        (
            "current_period.paid.expense_total",
            "Despesas pagas no período",
            "transactions",
        ),
        ("current_period.paid.balance", "Saldo pago no período", "general"),
        (
            "current_period.commitments.pending_expense_total",
            "Compromissos pendentes",
            "transactions",
        ),
        (
            "current_period.commitments.overdue_expense_total",
            "Despesas vencidas",
            "transactions",
        ),
        ("transactions.included_count", "Transações consideradas", "transactions"),
        ("wallet.total_value", "Valor total da carteira", "general"),
    )
    items = [
        item
        for path, label, dimension in evidence_paths
        if (
            item := _evidence_item(
                snapshot=snapshot,
                path=path,
                label=label,
                dimension=dimension,
            )
        )
        is not None
    ]

    for index, budget in enumerate(snapshot.get("budgets") or []):
        if isinstance(budget, dict):
            items.append(
                {
                    "path": f"budgets.{index}",
                    "label": str(budget.get("name") or "Orçamento"),
                    "dimension": "budgets",
                    "value": budget,
                }
            )

    for index, goal in enumerate(snapshot.get("goals") or []):
        if isinstance(goal, dict):
            items.append(
                {
                    "path": f"goals.{index}",
                    "label": str(goal.get("title") or "Meta"),
                    "dimension": "goals",
                    "value": goal,
                }
            )

    for index, card in enumerate(snapshot.get("credit_cards") or []):
        if isinstance(card, dict):
            items.append(
                {
                    "path": f"credit_cards.{index}",
                    "label": str(card.get("name") or "Cartão"),
                    "dimension": "credit_cards",
                    "value": card,
                }
            )

    return {
        "schema_version": EVIDENCE_MANIFEST_VERSION,
        "snapshot_hash": snapshot_hash,
        "items": items,
    }


def build_deterministic_risks(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    """Return deterministic risk flags derived from the snapshot."""

    risk_flags = _financial_health_risk_flags(snapshot)
    if risk_flags is not None:
        return risk_flags

    risks: list[dict[str, Any]] = []
    data_quality = snapshot.get("data_quality") or {}
    if isinstance(data_quality, dict) and data_quality.get("has_transactions") is False:
        risks.append(
            {
                "code": "insufficient_transaction_data",
                "severity": "info",
                "dimension": "general",
                "evidence": ["data_quality.has_transactions"],
            }
        )

    balance = _safe_float(_get_path(snapshot, "current_period.paid.balance"))
    if balance < 0:
        risks.append(
            {
                "code": "negative_paid_balance",
                "severity": "high",
                "dimension": "general",
                "evidence": ["current_period.paid.balance"],
            }
        )

    overdue = _safe_float(
        _get_path(snapshot, "current_period.commitments.overdue_expense_total")
    )
    if overdue > 0:
        risks.append(
            {
                "code": "overdue_expenses",
                "severity": "high",
                "dimension": "transactions",
                "evidence": ["current_period.commitments.overdue_expense_total"],
            }
        )

    pending = _safe_float(
        _get_path(snapshot, "current_period.commitments.pending_expense_total")
    )
    if pending > 0:
        risks.append(
            {
                "code": "future_commitments_open",
                "severity": "low",
                "dimension": "transactions",
                "evidence": [
                    "current_period.commitments.pending_expense_total",
                ],
            }
        )

    for index, budget in enumerate(snapshot.get("budgets") or []):
        if isinstance(budget, dict) and bool(budget.get("exceeded")):
            risks.append(
                {
                    "code": "budget_exceeded",
                    "severity": "medium",
                    "dimension": "budgets",
                    "evidence": [f"budgets.{index}.exceeded"],
                }
            )

    for index, card in enumerate(snapshot.get("credit_cards") or []):
        if isinstance(card, dict) and _safe_float(card.get("utilization_pct")) >= 80:
            risks.append(
                {
                    "code": "high_credit_card_utilization",
                    "severity": "medium",
                    "dimension": "credit_cards",
                    "evidence": [f"credit_cards.{index}.utilization_pct"],
                }
            )

    return risks


def build_ai_insight_preview(
    *,
    user_id: UUID,
    period_type: str,
    anchor_date: date | None = None,
) -> dict[str, Any]:
    """Create an auditable preview run without calling the LLM provider."""

    if db.session.get(User, user_id) is None:
        raise ValueError("user_id não encontrado")

    insight_type = _normalize_insight_type(period_type)
    anchor = anchor_date or date.today()
    previous = _get_latest_insight(user_id=user_id)
    raw_snapshot = _build_period_snapshot(
        insight_type=insight_type,
        user_id=user_id,
        anchor=anchor,
        previous_generated_at=previous.created_at if previous else None,
    )
    prompt_snapshot = minimize_prompt_data(raw_snapshot)
    prompt_snapshot, truncation_info = truncate_snapshot(prompt_snapshot)
    snapshot_hash = _financial_context_hash(prompt_snapshot)
    evidence_manifest = build_evidence_manifest(
        snapshot=prompt_snapshot,
        snapshot_hash=snapshot_hash,
    )
    risks = build_deterministic_risks(prompt_snapshot)

    period = prompt_snapshot["period"]
    period_label = str(period["label"])
    period_start = date.fromisoformat(str(period["start"]))
    period_end = date.fromisoformat(str(period["end"]))
    data_quality = prompt_snapshot.get("data_quality") or {}

    run = create_ai_insight_run(
        user_id=user_id,
        status=AIInsightRunStatus.previewed,
        period_type=insight_type,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        snapshot_schema_version=str(prompt_snapshot["schema_version"]),
        snapshot_hash=snapshot_hash,
        previous_snapshot_hash=_latest_snapshot_hash(
            user_id=user_id,
            period_type=insight_type,
        ),
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        snapshot_json=prompt_snapshot,
        evidence_manifest_json=evidence_manifest,
        data_quality_json=data_quality,
        truncation_flags_json=truncation_info,
    )

    return {
        "run_id": str(run.id),
        "status": run.status.value,
        "period_type": insight_type.value,
        "period_label": period_label,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "snapshot_hash": snapshot_hash,
        "previous_snapshot_hash": run.previous_snapshot_hash,
        "prompt_template_version": run.prompt_template_version,
        "snapshot": _json_safe(prompt_snapshot),
        "comparisons": _json_safe(prompt_snapshot.get("comparisons") or {}),
        "risks": _json_safe(risks),
        "evidence_manifest": _json_safe(evidence_manifest),
        "data_quality": _json_safe(data_quality),
        "truncation": _json_safe(truncation_info),
    }


def serialize_ai_insight_run_dossier(run: AIInsightRun) -> dict[str, Any]:
    """Serialize an AIInsightRun dossier without exposing raw prompts."""

    insight = (
        db.session.get(AIInsight, run.ai_insight_id) if run.ai_insight_id else None
    )
    payload: dict[str, Any] = {
        "run": {
            "id": str(run.id),
            "user_id": str(run.user_id),
            "ai_insight_id": str(run.ai_insight_id) if run.ai_insight_id else None,
            "status": run.status.value,
            "period_type": run.period_type.value,
            "period_label": run.period_label,
            "period_start": _date_iso(run.period_start),
            "period_end": _date_iso(run.period_end),
            "snapshot_schema_version": run.snapshot_schema_version,
            "snapshot_hash": run.snapshot_hash,
            "previous_snapshot_hash": run.previous_snapshot_hash,
            "prompt_template_version": run.prompt_template_version,
            "model": run.model,
            "tokens_in": int(run.tokens_in or 0),
            "tokens_out": int(run.tokens_out or 0),
            "tokens_total": int(run.tokens_total or 0),
            "cost_usd": float(run.cost_usd or 0),
            "created_at": _date_iso(run.created_at),
            "expires_at": _date_iso(run.expires_at),
            "purged_at": _date_iso(run.purged_at),
        },
        "snapshot": run.snapshot_json or {},
        "evidence_manifest": run.evidence_manifest_json or {},
        "data_quality": run.data_quality_json or {},
        "truncation": run.truncation_flags_json or {},
        "rejection_reasons": run.rejection_reasons_json or [],
        "insight": None,
    }
    if insight is not None:
        payload["insight"] = {
            "id": str(insight.id),
            "insight_type": insight.insight_type.value,
            "period_label": insight.period_label,
            "model": insight.model,
            "tokens_used": int(insight.tokens_used or 0),
            "cost_usd": float(insight.cost_usd or 0),
            "content": insight.content,
            "metadata": insight.metadata_dict,
            "created_at": _date_iso(insight.created_at),
        }
    return _json_safe_dict(payload)


def get_ai_insight_run_dossier(
    *,
    run_id: UUID | None = None,
    user_id: UUID | None = None,
    period_type: str | None = None,
    period_label: str | None = None,
    insight_id: UUID | None = None,
) -> dict[str, Any]:
    """Return the most recent run dossier matching the supplied selector."""

    query = AIInsightRun.query
    if run_id is not None:
        query = query.filter(AIInsightRun.id == run_id)
    if user_id is not None:
        query = query.filter(AIInsightRun.user_id == user_id)
    if period_type:
        query = query.filter(
            AIInsightRun.period_type == _normalize_insight_type(period_type)
        )
    if period_label:
        query = query.filter(AIInsightRun.period_label == period_label)
    if insight_id is not None:
        query = query.filter(AIInsightRun.ai_insight_id == insight_id)

    run = query.order_by(AIInsightRun.created_at.desc()).first()
    if run is None:
        raise ValueError("AIInsightRun não encontrado")
    return serialize_ai_insight_run_dossier(run)


__all__ = [
    "PROMPT_TEMPLATE_VERSION",
    "build_ai_insight_preview",
    "build_deterministic_risks",
    "build_evidence_manifest",
    "get_ai_insight_run_dossier",
    "serialize_ai_insight_run_dossier",
]
