"""Flask CLI command to start the RQ background worker (ARC-API-02)."""

from __future__ import annotations

import os

import click
from flask.cli import with_appcontext


@click.group("worker")
def worker_cli_group() -> None:
    """Manage the async background worker."""


@worker_cli_group.command("run")
@click.option(
    "--queue",
    default=os.getenv("RQ_QUEUE_NAME", "auraxis_outbound"),
    show_default=True,
    help="RQ queue name to consume.",
)
@click.option(
    "--burst",
    is_flag=True,
    default=False,
    help="Exit after processing all queued jobs (useful for CI / one-shot runs).",
)
@with_appcontext
def run_worker(queue: str, burst: bool) -> None:
    """Start the RQ worker for the *auraxis_outbound* queue."""
    import redis
    import rq

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    conn = redis.Redis.from_url(redis_url, decode_responses=False)
    rq_queue = rq.Queue(queue, connection=conn)
    worker = rq.Worker([rq_queue], connection=conn)
    click.echo(f"Starting RQ worker — queue={queue} burst={burst} redis={redis_url}")
    worker.work(burst=burst)
