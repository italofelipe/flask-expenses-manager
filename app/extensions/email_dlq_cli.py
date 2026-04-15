"""Flask CLI — Email DLQ management (issue #1049).

Commands
--------
    flask admin email-dlq list    — list pending messages (up to 100)
    flask admin email-dlq retry   — retry all pending messages
    flask admin email-dlq size    — print current queue size
"""

from __future__ import annotations

import json

import click
from flask import Flask
from flask.cli import AppGroup

email_dlq_cli = AppGroup("email-dlq", help="Email Dead-Letter Queue management.")


@email_dlq_cli.command("list")
def dlq_list() -> None:
    """List up to 100 pending messages in the DLQ."""
    from app.services.email_dlq import get_email_dlq

    dlq = get_email_dlq()
    if not dlq.available:
        click.echo("DLQ unavailable (Redis not configured).", err=True)
        return

    entries = dlq.list_pending()
    if not entries:
        click.echo("DLQ is empty.")
        return

    click.echo(f"{len(entries)} pending message(s):\n")
    for i, entry in enumerate(entries, 1):
        click.echo(f"[{i}] {json.dumps(entry, indent=2, default=str)}")


@email_dlq_cli.command("retry")
@click.option(
    "--limit",
    default=50,
    show_default=True,
    help="Maximum number of messages to retry in this run.",
)
def dlq_retry(limit: int) -> None:
    """Retry up to LIMIT pending messages from the DLQ."""
    from app.services.email_dlq import get_email_dlq

    dlq = get_email_dlq()
    if not dlq.available:
        click.echo("DLQ unavailable (Redis not configured).", err=True)
        return

    size_before = dlq.size()
    click.echo(f"DLQ size before retry: {size_before}")

    if size_before == 0:
        click.echo("Nothing to retry.")
        return

    delivered = dlq.retry_pending(limit=limit)
    size_after = dlq.size()
    click.echo(f"Delivered: {delivered} | Remaining: {size_after}")


@email_dlq_cli.command("size")
def dlq_size() -> None:
    """Print the current number of messages in the DLQ."""
    from app.services.email_dlq import get_email_dlq

    dlq = get_email_dlq()
    if not dlq.available:
        click.echo("DLQ unavailable (Redis not configured).", err=True)
        return

    click.echo(f"email_dlq_size={dlq.size()}")


def register_email_dlq_commands(app: Flask) -> None:
    """Register the ``email-dlq`` CLI group.

    Registered as ``flask email-dlq`` (standalone group).
    """
    app.cli.add_command(email_dlq_cli, "email-dlq")
