"""Monthly AI financial report orchestration.

This service keeps the monthly report flow auditable without adding a new
storage model: ``AIInsightRun`` is the traceable job/run record, ``AIInsight``
is the displayable report, and ``LLMAuditLog`` remains the token/cost ledger
through ``AIAdvisoryService``.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from typing import Any, cast
from uuid import UUID

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.ai_insight_run import AIInsightRun, AIInsightRunStatus
from app.models.user import User
from app.services.ai_advisory_service import (
    AIAdvisoryService,
    _build_period_snapshot,
    _financial_context_hash,
    _get_latest_insight_for_period_context,
)
from app.services.ai_insight_audit import (
    PROMPT_TEMPLATE_VERSION,
    _latest_snapshot_hash,
    build_evidence_manifest,
)
from app.services.ai_insight_runs import create_ai_insight_run
from app.services.ai_lgpd import minimize_prompt_data, minimize_text
from app.services.email_templates.base import render_monthly_analysis_ready_email
from app.services.financial_insight_context_builder import truncate_snapshot
from app.services.llm_provider import LLMProvider
from app.services.outbound_queue import get_default_outbound_queue

log = logging.getLogger(__name__)

_MONTHLY_CONTEXT_VERSION = "monthly_ai_report_context.v1"
_DEFAULT_APP_URL = "https://app.auraxis.com.br"
_QUEUE_NAME = os.getenv("RQ_QUEUE_NAME", "auraxis_outbound")
_JOB_TIMEOUT = "20m"


def _month_bounds(anchor_date: date) -> tuple[date, date]:
    if anchor_date.month == 12:
        next_month = date(anchor_date.year + 1, 1, 1)
    else:
        next_month = date(anchor_date.year, anchor_date.month + 1, 1)
    start = date(anchor_date.year, anchor_date.month, 1)
    return start, next_month.fromordinal(next_month.toordinal() - 1)


def _safe_json_loads(value: str) -> dict[str, Any]:
    try:
        decoded = json.loads(value)
    except (TypeError, ValueError):
        return {}
    return decoded if isinstance(decoded, dict) else {}


def _extract_insight_content(
    insight: AIInsight,
) -> tuple[str | None, list[dict[str, Any]]]:
    payload = _safe_json_loads(insight.content)
    summary = (
        payload.get("summary") if isinstance(payload.get("summary"), str) else None
    )
    raw_items = payload.get("items")
    items = (
        [item for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, list)
        else []
    )
    return summary, items


def _summarize_insight(insight: AIInsight) -> dict[str, Any]:
    summary, items = _extract_insight_content(insight)
    dimensions = sorted(
        {
            str(item.get("dimension") or "general")
            for item in items
            if isinstance(item, dict)
        }
    )
    return {
        "period_label": insight.period_label,
        "period_start": insight.period_start.isoformat(),
        "period_end": insight.period_end.isoformat(),
        "summary": minimize_text(summary or "")[:1200],
        "dimensions": dimensions,
        "item_count": len(items),
    }


def _daily_insights_for_month(
    *,
    user_id: UUID,
    period_start: date,
    period_end: date,
) -> list[AIInsight]:
    return cast(
        list[AIInsight],
        AIInsight.query.filter_by(user_id=user_id, insight_type=InsightType.daily)
        .filter(AIInsight.period_start >= period_start)
        .filter(AIInsight.period_end <= period_end)
        .order_by(AIInsight.period_start.asc(), AIInsight.created_at.asc())
        .all(),
    )


def _previous_monthly_insight(
    *,
    user_id: UUID,
    period_start: date,
) -> AIInsight | None:
    return cast(
        AIInsight | None,
        AIInsight.query.filter_by(user_id=user_id, insight_type=InsightType.monthly)
        .filter(AIInsight.period_end < period_start)
        .order_by(AIInsight.period_end.desc(), AIInsight.created_at.desc())
        .first(),
    )


def _monthly_report_context(
    *,
    user_id: UUID,
    period_start: date,
    period_end: date,
) -> dict[str, Any]:
    daily = _daily_insights_for_month(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    )
    previous = _previous_monthly_insight(
        user_id=user_id,
        period_start=period_start,
    )
    previous_payload = _summarize_insight(previous) if previous else None
    return {
        "schema_version": _MONTHLY_CONTEXT_VERSION,
        "daily_insights": [_summarize_insight(item) for item in daily],
        "daily_insight_count": len(daily),
        "previous_monthly_insight": previous_payload,
        "comparison_scope": {
            "current_month": f"{period_start:%Y-%m}",
            "previous_month": previous.period_label if previous else None,
            "instruction": (
                "Compare o mês atual com o relatório mensal anterior quando "
                "existir e use os insights diários como trilha narrativa."
            ),
        },
    }


def _build_monthly_prompt_snapshot(
    *,
    user_id: UUID,
    anchor_date: date,
) -> tuple[dict[str, Any], dict[str, Any], str, date, date, str, str]:
    period_start, period_end = _month_bounds(anchor_date)
    previous = _get_latest_insight_for_period_context(
        user_id=user_id,
        insight_type=InsightType.monthly,
        period_label=f"{anchor_date:%Y-%m}",
    )
    raw_snapshot = _build_period_snapshot(
        insight_type=InsightType.monthly,
        user_id=user_id,
        anchor=anchor_date,
        previous_generated_at=previous.created_at if previous else None,
    )
    raw_snapshot["monthly_report_context"] = _monthly_report_context(
        user_id=user_id,
        period_start=period_start,
        period_end=period_end,
    )
    prompt_snapshot = minimize_prompt_data(raw_snapshot)
    prompt_snapshot, truncation_info = truncate_snapshot(prompt_snapshot)
    snapshot_hash = _financial_context_hash(prompt_snapshot)
    context_version = str(prompt_snapshot["schema_version"])
    period = prompt_snapshot["period"]
    period_label = str(period["label"])
    return (
        prompt_snapshot,
        truncation_info,
        snapshot_hash,
        date.fromisoformat(str(period["start"])),
        date.fromisoformat(str(period["end"])),
        period_label,
        context_version,
    )


def create_monthly_report_run(
    *,
    user_id: UUID,
    anchor_date: date | None = None,
) -> dict[str, Any]:
    """Create an auditable monthly report run without calling the LLM."""

    if db.session.get(User, user_id) is None:
        raise ValueError("user_id não encontrado")

    anchor = anchor_date or date.today()
    (
        prompt_snapshot,
        truncation_info,
        snapshot_hash,
        period_start,
        period_end,
        period_label,
        context_version,
    ) = _build_monthly_prompt_snapshot(user_id=user_id, anchor_date=anchor)
    evidence_manifest = build_evidence_manifest(
        snapshot=prompt_snapshot,
        snapshot_hash=snapshot_hash,
    )
    data_quality = prompt_snapshot.get("data_quality") or {}

    run = create_ai_insight_run(
        user_id=user_id,
        status=AIInsightRunStatus.previewed,
        period_type=InsightType.monthly,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        snapshot_schema_version=context_version,
        snapshot_hash=snapshot_hash,
        previous_snapshot_hash=_latest_snapshot_hash(
            user_id=user_id,
            period_type=InsightType.monthly,
        ),
        prompt_template_version=PROMPT_TEMPLATE_VERSION,
        snapshot_json=prompt_snapshot,
        evidence_manifest_json=evidence_manifest,
        data_quality_json=data_quality,
        truncation_flags_json=truncation_info,
    )

    return _serialize_run(run, include_snapshot=True)


def _app_deep_link(insight_id: UUID) -> str:
    base_url = os.getenv("AURAXIS_APP_URL", _DEFAULT_APP_URL).rstrip("/")
    return f"{base_url}/insights?open={insight_id}"


def _summary_preview(summary: object) -> str:
    text = " ".join(str(summary or "").split())
    if not text:
        return "Seu relatório mensal já está disponível no Auraxis."
    if len(text) <= 360:
        return text
    return text[:359].rsplit(" ", 1)[0].rstrip() + "..."


def _first_name(user: User) -> str:
    return (str(user.name or "").strip().split(" ", 1)[0] or "Tudo bem").strip()


def _send_monthly_report_email(
    *,
    user: User,
    insight_id: UUID,
    summary: object,
) -> str | None:
    deep_link = _app_deep_link(insight_id)
    html, text = render_monthly_analysis_ready_email(
        first_name=_first_name(user),
        summary_preview=_summary_preview(summary),
        insight_url=deep_link,
    )
    job_id = get_default_outbound_queue().enqueue_send_email(
        to_email=user.email,
        subject="Seu relatório mensal Auraxis está pronto",
        html=html,
        text=text,
        tag="monthly_ai_insight_ready",
    )
    return str(job_id) if job_id is not None else None


def process_monthly_report_run(
    *,
    run_id: UUID,
    llm_provider: LLMProvider | None = None,
) -> dict[str, Any]:
    """Generate a monthly report from an existing run and notify the user."""

    run = db.session.get(AIInsightRun, run_id)
    if run is None or run.period_type != InsightType.monthly:
        raise ValueError("run_id inválido")

    if run.status in {AIInsightRunStatus.generated, AIInsightRunStatus.cached}:
        return _serialize_run_result(run)
    if run.status != AIInsightRunStatus.previewed:
        raise ValueError("run não está disponível para geração")

    try:
        service = AIAdvisoryService(user_id=run.user_id, llm_provider=llm_provider)
        result = service.generate_financial_insights(
            period_type=InsightType.monthly.value,
            anchor_date=run.period_start,
            preview_run_id=run.id,
        )
        db.session.refresh(run)
        user = db.session.get(User, run.user_id)
        if user is not None and run.ai_insight_id is not None:
            email_job_id = _send_monthly_report_email(
                user=user,
                insight_id=run.ai_insight_id,
                summary=result.get("summary"),
            )
        else:
            email_job_id = None
        payload = _serialize_run_result(run)
        payload["email_job_id"] = email_job_id
        return payload
    except Exception as exc:
        run.status = AIInsightRunStatus.failed
        run.rejection_reasons_json = [str(exc)]
        db.session.commit()
        log.warning(
            "ai_monthly_report.process_failed run_id=%s user_id=%s error=%s",
            run.id,
            run.user_id,
            exc,
        )
        raise


def enqueue_monthly_report_run(*, run_id: UUID) -> dict[str, Any]:
    """Queue a monthly report run, falling back to sync processing locally."""

    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return process_monthly_report_run(run_id=run_id)

    import redis as redis_lib
    import rq

    try:
        queue = rq.Queue(_QUEUE_NAME, connection=redis_lib.Redis.from_url(redis_url))
        job = queue.enqueue(
            "app.jobs.ai_insight_jobs.generate_monthly_report",
            str(run_id),
            job_timeout=_JOB_TIMEOUT,
        )
    except Exception as exc:
        log.warning(
            "ai_monthly_report.enqueue_failed run_id=%s fallback=sync error=%s",
            run_id,
            exc,
        )
        return process_monthly_report_run(run_id=run_id)

    run = db.session.get(AIInsightRun, run_id)
    payload: dict[str, Any] = (
        _serialize_run(run) if run is not None else {"run_id": str(run_id)}
    )
    payload["queued"] = True
    payload["job_id"] = str(job.id)
    return payload


def _serialize_run(
    run: AIInsightRun, *, include_snapshot: bool = False
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "run_id": str(run.id),
        "status": run.status.value,
        "period_type": run.period_type.value,
        "period_label": run.period_label,
        "period_start": run.period_start.isoformat(),
        "period_end": run.period_end.isoformat(),
        "snapshot_hash": run.snapshot_hash,
        "previous_snapshot_hash": run.previous_snapshot_hash,
        "ai_insight_id": str(run.ai_insight_id) if run.ai_insight_id else None,
    }
    if include_snapshot:
        payload["snapshot"] = run.snapshot_json
        payload["data_quality"] = run.data_quality_json or {}
        payload["truncation"] = run.truncation_flags_json or {}
    return payload


def _serialize_run_result(run: AIInsightRun) -> dict[str, Any]:
    payload = _serialize_run(run)
    payload["insight_id"] = str(run.ai_insight_id) if run.ai_insight_id else None
    payload["deep_link"] = (
        _app_deep_link(run.ai_insight_id) if run.ai_insight_id is not None else None
    )
    return payload


def get_monthly_report_run_status(*, user_id: UUID, run_id: UUID) -> dict[str, Any]:
    run = db.session.get(AIInsightRun, run_id)
    if run is None or run.user_id != user_id:
        raise ValueError("run_id não encontrado")
    return _serialize_run_result(run)


def get_ai_insight_by_id(*, user_id: UUID, insight_id: UUID) -> dict[str, Any]:
    insight = db.session.get(AIInsight, insight_id)
    if insight is None or insight.user_id != user_id:
        raise ValueError("insight_id não encontrado")
    summary, items = _extract_insight_content(insight)
    metadata = insight.metadata_dict
    return {
        "id": str(insight.id),
        "content": insight.content,
        "summary": summary,
        "items": items,
        "insight_type": insight.insight_type.value,
        "period_type": insight.insight_type.value,
        "period_label": insight.period_label,
        "period_start": insight.period_start.isoformat(),
        "period_end": insight.period_end.isoformat(),
        "context_schema_version": metadata.get("context_schema_version"),
        "context_hash": metadata.get("context_hash"),
        "model": insight.model,
        "tokens_used": insight.tokens_used,
        "cost_usd": float(insight.cost_usd),
        "created_at": insight.created_at.isoformat() if insight.created_at else None,
    }


__all__ = [
    "create_monthly_report_run",
    "enqueue_monthly_report_run",
    "get_ai_insight_by_id",
    "get_monthly_report_run_status",
    "process_monthly_report_run",
]
