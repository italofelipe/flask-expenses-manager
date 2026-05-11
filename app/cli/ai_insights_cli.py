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
from app.models.entitlement import Entitlement
from app.models.llm_audit_log import LLMAuditLog
from app.models.user import User
from app.services.ai_advisory_service import AIAdvisoryService
from app.services.llm_provider import LLMProviderError

ai_insights_cli = AppGroup("ai", help="Scheduled AI insights batch commands.")

_BRT = timezone(timedelta(hours=-3))
_WEEKLY_ENDPOINT = "weekly_summary_batch"
_MONTHLY_ENDPOINT = "spending_insights_batch"


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


def _already_run_today(user_id: uuid.UUID, endpoint: str) -> bool:
    """Return True if a batch insight was already generated today (BRT)."""
    today = _brt_today()
    exists = (
        db.session.query(LLMAuditLog.id)
        .filter(
            LLMAuditLog.user_id == user_id,
            LLMAuditLog.endpoint == endpoint,
            db.func.date(LLMAuditLog.created_at) == today,
        )
        .first()
    )
    return exists is not None


def _run_batch(
    *,
    user_ids: list[uuid.UUID],
    endpoint: str,
    generate_fn_name: str,
    label: str,
    dry_run: bool,
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
            f"{label} dry-run: {len(user_ids)} eligible Premium users — no calls made."
        )
        return 0

    processed = 0
    failures = 0
    skipped = 0
    total_cost = 0.0

    for user_id in user_ids:
        if _already_run_today(user_id, endpoint):
            skipped += 1
            continue

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = getattr(service, generate_fn_name)()
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
        f"skipped={skipped} cost_usd={total_cost:.6f}"
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
        endpoint=_WEEKLY_ENDPOINT,
        generate_fn_name="generate_weekly_summary_narrative",
        label="weekly_insights",
        dry_run=dry_run,
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
    if month is None:
        today = _brt_today()
        first_of_month = today.replace(day=1)
        prev_month_last = first_of_month - timedelta(days=1)
        month = prev_month_last.strftime("%Y-%m")

    user_ids = _all_active_user_ids()

    if dry_run:
        click.echo(
            f"monthly_insights dry-run: {len(user_ids)} eligible users "
            f"(Free + Premium) for month={month} — no calls made."
        )
        sys.exit(0)

    processed = 0
    failures = 0
    skipped = 0
    total_cost = 0.0

    for user_id in user_ids:
        if _already_run_today(user_id, _MONTHLY_ENDPOINT):
            skipped += 1
            continue

        service = AIAdvisoryService(user_id=user_id)
        try:
            result = service.generate_spending_insights(month=month)
            total_cost += float(result.get("cost_usd", 0))
            processed += 1
        except (LLMProviderError, Exception) as exc:  # noqa: BLE001
            click.echo(
                f"monthly_insights ERROR user={user_id} error={exc}",
                err=True,
            )
            failures += 1

    click.echo(
        f"monthly_insights: processed={processed} failures={failures} "
        f"skipped={skipped} cost_usd={total_cost:.6f} month={month}"
    )

    if failures > 0 and processed == 0 and skipped == 0:
        sys.exit(1)


def register_ai_insights_commands(app: Flask) -> None:
    """Register the ``ai`` CLI group on *app*."""
    app.cli.add_command(ai_insights_cli)


__all__ = [
    "ai_insights_cli",
    "register_ai_insights_commands",
]
