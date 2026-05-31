from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.extensions.database import db
from app.extensions.prometheus_metrics import (
    record_ai_insight_cost,
    record_ai_insight_data_quality,
    record_ai_insight_run,
    record_ai_insight_runs_purged,
    record_ai_insight_truncated,
)
from app.models.ai_insight import InsightType
from app.models.ai_insight_run import (
    DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS,
    AIInsightRun,
    AIInsightRunStatus,
)
from app.utils.datetime_utils import utc_now_naive

log = logging.getLogger(__name__)


def _count_domains_present(data_quality_json: Any) -> int:
    """Count financial domains flagged present in ``data_quality.domain_presence``.

    Defensive against shape drift: a domain counts as present when its value is
    truthy, or (when a dict) when its ``present``/``available`` field is truthy.
    Returns 0 when the structure is missing or unrecognised. No PII is read.
    """
    if not isinstance(data_quality_json, dict):
        return 0
    presence = data_quality_json.get("domain_presence")
    if not isinstance(presence, dict):
        return 0
    count = 0
    for value in presence.values():
        if isinstance(value, dict):
            if value.get("present") or value.get("available") or value.get("has_data"):
                count += 1
        elif value:
            count += 1
    return count


def _is_truncated(truncation_flags_json: Any) -> bool:
    return bool(
        isinstance(truncation_flags_json, dict)
        and truncation_flags_json.get("truncated")
    )


_EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_LONG_NUMBER_RE = re.compile(r"\b\d{8,}\b")
_FORBIDDEN_SNAPSHOT_KEYS = frozenset(
    {
        "id",
        "user_id",
        "owner_id",
        "from_user_id",
        "to_user_id",
        "external_id",
        "email",
        "phone",
        "telefone",
        "document",
        "documento",
        "cpf",
        "cnpj",
        "bank",
        "bank_name",
        "raw_bank_name",
        "account_id",
        "credit_card_id",
        "transaction_id",
    }
)


def _is_forbidden_snapshot_key(key: object) -> bool:
    normalized = str(key).strip().lower()
    if normalized in _FORBIDDEN_SNAPSHOT_KEYS:
        return True
    return normalized.endswith("_id")


def _sanitize_text(value: str, *, max_length: int = 160) -> str:
    text = " ".join(value.split())
    text = _EMAIL_RE.sub("[email]", text)
    text = _CPF_RE.sub("[cpf]", text)
    text = _LONG_NUMBER_RE.sub("[number]", text)
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "..."
    return text


def sanitize_audit_snapshot(value: Any) -> Any:
    """Return a recursively sanitized snapshot suitable for AIInsightRun.

    The financial snapshot is allowed to keep deterministic facts such as
    amounts, dates, status and categories. It must not persist identifiers or
    free-text PII in the auditable run payload.
    """

    if isinstance(value, dict):
        return {
            key: sanitize_audit_snapshot(child)
            for key, child in value.items()
            if not _is_forbidden_snapshot_key(key)
        }
    if isinstance(value, list):
        return [sanitize_audit_snapshot(item) for item in value]
    if isinstance(value, str):
        return _sanitize_text(value)
    return value


def create_ai_insight_run(
    *,
    user_id: UUID,
    status: AIInsightRunStatus,
    period_type: InsightType,
    period_label: str,
    period_start: date,
    period_end: date,
    snapshot_schema_version: str,
    snapshot_hash: str,
    prompt_template_version: str,
    ai_insight_id: UUID | None = None,
    previous_snapshot_hash: str | None = None,
    snapshot_json: Any | None = None,
    evidence_manifest_json: Any | None = None,
    data_quality_json: Any | None = None,
    rejection_reasons_json: Any | None = None,
    truncation_flags_json: Any | None = None,
    model: str | None = None,
    tokens_in: int = 0,
    tokens_out: int = 0,
    tokens_total: int = 0,
    cost_usd: Decimal | float | str = Decimal("0"),
    commit: bool = True,
) -> AIInsightRun:
    """Persist an AIInsightRun with sanitized audit payloads."""

    run = AIInsightRun(
        user_id=user_id,
        ai_insight_id=ai_insight_id,
        status=status,
        period_type=period_type,
        period_label=period_label,
        period_start=period_start,
        period_end=period_end,
        snapshot_schema_version=snapshot_schema_version,
        snapshot_hash=snapshot_hash,
        previous_snapshot_hash=previous_snapshot_hash,
        prompt_template_version=prompt_template_version,
        snapshot_json=sanitize_audit_snapshot(snapshot_json),
        evidence_manifest_json=sanitize_audit_snapshot(evidence_manifest_json),
        data_quality_json=data_quality_json,
        rejection_reasons_json=rejection_reasons_json or [],
        truncation_flags_json=truncation_flags_json or {},
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        tokens_total=tokens_total,
        cost_usd=Decimal(str(cost_usd)),
    )
    db.session.add(run)
    if commit:
        db.session.commit()

    # #1314 — observability: emit lifecycle/quality metrics + a PII-free
    # structured log keyed by run_id/snapshot_hash. snapshot_json itself is
    # never logged (it carries deterministic facts but we keep logs lean).
    period_value = period_type.value
    record_ai_insight_run(status=status.value, period_type=period_value)
    if _is_truncated(truncation_flags_json):
        record_ai_insight_truncated(period_type=period_value)
    domains_present = _count_domains_present(data_quality_json)
    record_ai_insight_data_quality(
        period_type=period_value,
        domains_present=domains_present,
    )
    cost_value = float(run.cost_usd)
    if cost_value > 0:
        record_ai_insight_cost(period_type=period_value, cost_usd=cost_value)
    log.info(
        "ai_insight.run.created run_id=%s status=%s period_type=%s "
        "period=%s snapshot_hash=%s tokens=%s cost_usd=%s truncated=%s "
        "domains_present=%s",
        run.id,
        status.value,
        period_value,
        period_label,
        snapshot_hash,
        run.tokens_total,
        cost_value,
        _is_truncated(truncation_flags_json),
        domains_present,
    )
    return run


def transition_ai_insight_run_status(
    run: AIInsightRun,
    new_status: AIInsightRunStatus,
    *,
    reason: str | None = None,
) -> None:
    """Move *run* to *new_status*, emitting the lifecycle metric + a log (#1314).

    Centralises status changes so every transition is observable. Callers keep
    setting their other side-effect fields (ai_insight_id, tokens, cost) around
    this call. The structured log uses run_id/snapshot_hash only — no PII.
    """
    run.status = new_status
    period_value = run.period_type.value
    record_ai_insight_run(status=new_status.value, period_type=period_value)
    cost_value = float(run.cost_usd)
    if new_status is AIInsightRunStatus.generated and cost_value > 0:
        record_ai_insight_cost(period_type=period_value, cost_usd=cost_value)
    log.info(
        "ai_insight.run.transition run_id=%s status=%s period_type=%s "
        "snapshot_hash=%s tokens=%s cost_usd=%s reason=%s",
        run.id,
        new_status.value,
        period_value,
        run.snapshot_hash,
        run.tokens_total,
        cost_value,
        reason or "",
    )


def purge_expired_ai_insight_runs(*, now: datetime | None = None) -> int:
    """Purge retained snapshot payloads whose audit retention window expired.

    The run row remains as a lightweight audit marker. Account deletion still
    hard-deletes the whole row through the LGPD registry.
    """

    purge_at = now or utc_now_naive()
    rows = (
        AIInsightRun.query.filter(AIInsightRun.expires_at <= purge_at)
        .filter(AIInsightRun.purged_at.is_(None))
        .all()
    )
    for row in rows:
        row.snapshot_json = None
        row.evidence_manifest_json = None
        row.status = AIInsightRunStatus.purged
        row.purged_at = purge_at
        record_ai_insight_run(
            status=AIInsightRunStatus.purged.value,
            period_type=row.period_type.value,
        )
    db.session.commit()
    purged = len(rows)
    record_ai_insight_runs_purged(purged)
    log.info("ai_insight.run.purged count=%s purge_at=%s", purged, purge_at)
    return purged


__all__ = [
    "DEFAULT_AI_INSIGHT_RUN_RETENTION_DAYS",
    "create_ai_insight_run",
    "purge_expired_ai_insight_runs",
    "sanitize_audit_snapshot",
    "transition_ai_insight_run_status",
]
