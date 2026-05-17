"""Flask CLI commands for scheduled AI insights batch jobs (#1215, #1216).

Commands:
  flask ai weekly-insights   — Premium users, runs every Saturday 03:00 UTC
  flask ai monthly-insights  — All users, runs on the 1st of each month 03:00 UTC

Both commands follow the same pattern:
  1. Query eligible users
  2. Check idempotency (skip if already generated today)
  3. Call AIAdvisoryService
  4. Log per-user result; continue on individual failures
  5. Exit non-zero if ALL users failed (total failure)
"""

from __future__ import annotations

import sys
import uuid
from datetime import date, datetime, timedelta, timezone

import click
from flask import Flask
from flask.cli import AppGroup

from app.extensions.database import db
from app.models.ai_insight import AIInsight, InsightType
from app.models.entitlement import Entitlement
from app.models.user import User
from app.services.ai_advisory_service import AIAdvisoryService
from app.services.llm_provider import LLMProviderError

ai_insights_cli = AppGroup("ai", help="Scheduled AI insights batch commands.")

_BRT = timezone(timedelta(hours=-3))


def _brt_today() -> date:
    return datetime.now(_BRT).date()


def _premium_user_ids() -> list[uuid.UUID]:
    """Return UUIDs of all non-deleted users with advanced_simulations entitlement."""
    rows = (
        db.session.query(Entitlement.user_id)
        .join(User, User.id == Entitlement.user_id)
        .filter(
            Entitlement.feature_key == "advanced_simulations",
            User.deleted_at.is_(None),
        )
        .distinct()
        .all()
    )
    return [r.user_id for r in rows]


def _all_active_user_ids() -> list[uuid.UUID]:
    """Return UUIDs of all non-deleted users (Free + Premium)."""
    rows = db.session.query(User.id).filter(User.deleted_at.is_(None)).all()
    return [r.id for r in rows]


def _monthly_anchor(month: str | None) -> date:
    if month is not None:
        year, mon = int(month[:4]), int(month[5:7])
        return date(year, mon, 1)

    today = _brt_today()
    first_of_month = today.replace(day=1)
    prev_month_last = first_of_month - timedelta(days=1)
    return prev_month_last.replace(day=1)


def _period_label(*, insight_type: InsightType, anchor_date: date) -> str:
    if insight_type == InsightType.weekly:
        iso = anchor_date.isocalendar()
        return f"{iso.year}-W{iso.week:02d}"
    if insight_type == InsightType.monthly:
        return anchor_date.strftime("%Y-%m")
    return anchor_date.isoformat()


def _already_has_insight(
    *,
    user_id: uuid.UUID,
    insight_type: InsightType,
    period_label: str,
) -> bool:
    exists = (
        db.session.query(AIInsight.id)
        .filter_by(
            user_id=user_id,
            insight_type=insight_type,
            period_label=period_label,
        )
        .first()
    )
    return exists is not None


def _run_batch(
    *,
    user_ids: list[uuid.UUID],
    insight_type: InsightType,
    anchor_date: date,
    label: str,
    dry_run: bool,
    dry_run_subject: str,
) -> int:
    """Run a batch insight generation job.

    Returns:
        Exit code: 0 if at least one user succeeded (or no users); 1 if all failed.
    """
    if not user_ids:
        click.echo(f"{label}: processed=0 failures=0 skipped=0 cost_usd=0.000000")
        return 0

    if dry_run:
        click.echo(
            f"{label} dry-run: {len(user_ids)} {dry_run_subject} — no calls made."
        )
        return 0

    period_label = _period_label(insight_type=insight_type, anchor_date=anchor_date)
    processed = 0
    failures = 0
    skipped = 0
    total_cost = 0.0

    for user_id in user_ids:
        if _already_has_insight(
            user_id=user_id,
            insight_type=insight_type,
            period_label=period_label,
        ):
            skipped += 1
            continue

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = service.generate_financial_insights(
                period_type=insight_type.value,
                anchor_date=anchor_date,
            )
            if result.get("cached") is True:
                skipped += 1
            else:
                total_cost += float(result.get("cost_usd", 0))
                processed += 1
        except (LLMProviderError, Exception) as exc:  # noqa: BLE001
            click.echo(
                f"{label} ERROR user={user_id} error={exc}",
                err=True,
            )
            failures += 1

    click.echo(
        f"{label}: processed={processed} failures={failures} "
        f"skipped={skipped} cost_usd={total_cost:.6f} period={period_label}"
    )

    if failures > 0 and processed == 0 and skipped == 0:
        return 1
    return 0


# ---------------------------------------------------------------------------
# weekly-insights command
# ---------------------------------------------------------------------------


@ai_insights_cli.command("weekly-insights")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print eligible user count without making LLM calls.",
)
def weekly_insights(dry_run: bool) -> None:
    """Generate weekly financial briefing for all Premium users.

    Intended to run every Saturday at 03:00 UTC (00:00 BRT).
    Idempotent: skips users who already have a weekly summary today.
    """
    user_ids = _premium_user_ids()
    exit_code = _run_batch(
        user_ids=user_ids,
        insight_type=InsightType.weekly,
        anchor_date=_brt_today(),
        label="weekly_insights",
        dry_run=dry_run,
        dry_run_subject="eligible Premium users",
    )
    sys.exit(exit_code)


# ---------------------------------------------------------------------------
# monthly-insights command
# ---------------------------------------------------------------------------


@ai_insights_cli.command("monthly-insights")
@click.option(
    "--month",
    default=None,
    metavar="YYYY-MM",
    help="Month to generate insights for. Defaults to the previous calendar month.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print eligible user count without making LLM calls.",
)
def monthly_insights(month: str | None, dry_run: bool) -> None:
    """Generate monthly spending recap for ALL active users (Free + Premium).

    Intended to run on the 1st of each month at 03:00 UTC (00:00 BRT).
    Idempotent: skips users who already have a monthly summary today.
    """
    anchor_date = _monthly_anchor(month)
    month_label = anchor_date.strftime("%Y-%m")
    user_ids = _all_active_user_ids()
    exit_code = _run_batch(
        user_ids=user_ids,
        insight_type=InsightType.monthly,
        anchor_date=anchor_date,
        label="monthly_insights",
        dry_run=dry_run,
        dry_run_subject=f"eligible users (Free + Premium) for month={month_label}",
    )
    if not dry_run:
        click.echo(f"monthly_insights month={month_label}")
    sys.exit(exit_code)


def register_ai_insights_commands(app: Flask) -> None:
    """Register the ``ai`` CLI group on *app*."""
    app.cli.add_command(ai_insights_cli)


__all__ = [
    "ai_insights_cli",
    "register_ai_insights_commands",
]
