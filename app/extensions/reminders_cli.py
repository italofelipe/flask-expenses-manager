"""Flask CLI command — transaction due-date reminders.

Dispatches email reminders for transactions approaching their due date:

    flask reminders dispatch-due-soon [--dry-run]

The underlying business logic lives in
``app.application.services.transaction_reminder_service``.
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup

reminders_cli = AppGroup("reminders", help="Transaction reminder commands.")


@reminders_cli.command("dispatch-due-soon")
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print what would be sent without dispatching emails.",
)
def dispatch_due_soon(dry_run: bool) -> None:
    """Send reminders for transactions due in 7 days and 1 day."""
    if dry_run:
        click.echo("[dry-run] Would dispatch reminders for 7-day and 1-day windows.")
        return

    from app.application.services.transaction_reminder_service import (
        dispatch_due_transaction_reminders,
    )

    for window in (7, 1):
        result = dispatch_due_transaction_reminders(days_before_due=window)
        click.echo(
            f"{window}-day reminders: "
            f"scanned={result.scanned} sent={result.sent} skipped={result.skipped}"
        )


def register_reminders_commands(app: Flask) -> None:
    """Register the ``reminders`` CLI group on *app*."""
    app.cli.add_command(reminders_cli)
