from __future__ import annotations

import json

import click
from flask import Flask

from app.extensions.integration_metrics import reset_metrics, snapshot_metrics


def register_integration_metrics_commands(app: Flask) -> None:
    @app.cli.group("integration-metrics")
    def integration_metrics_group() -> None:
        """Operational commands for integration counters."""

    @integration_metrics_group.command("snapshot")
    @click.option(
        "--prefix",
        default="",
        help="Filter counters by prefix (ex.: brapi. or rate_limit.).",
    )
    @click.option(
        "--reset",
        is_flag=True,
        default=False,
        help="Reset counters after emitting the snapshot.",
    )
    def integration_metrics_snapshot(prefix: str, reset: bool) -> None:
        normalized_prefix = prefix.strip() or None
        counters = snapshot_metrics(prefix=normalized_prefix)
        payload = {
            "prefix": normalized_prefix,
            "counters": counters,
            "total": sum(counters.values()),
        }
        click.echo(json.dumps(payload, sort_keys=True))
        if reset:
            reset_metrics()
