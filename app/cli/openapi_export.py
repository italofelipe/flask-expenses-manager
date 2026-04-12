"""Flask CLI command — deterministic OpenAPI JSON export.

    flask openapi-export --output openapi.json

Produces a stable, reproducible OpenAPI 3.0 JSON file from the live apispec
registration.  Two consecutive runs must yield byte-identical output (sorted
keys, no timestamps, deterministic numeric coercion).
"""

from __future__ import annotations

import json

import click
from flask import current_app
from flask.cli import with_appcontext


@click.command("openapi-export")
@click.option(
    "--output",
    "-o",
    default="openapi.json",
    show_default=True,
    help="Output file path for the OpenAPI JSON.",
)
@with_appcontext
def openapi_export_command(output: str) -> None:
    """Export the current OpenAPI spec to a deterministic JSON file."""
    with current_app.test_client() as client:
        response = client.get("/docs/swagger/")
        if response.status_code != 200:
            raise click.ClickException(
                f"Swagger endpoint returned HTTP {response.status_code}"
            )
        spec = response.get_json()
        if not spec:
            raise click.ClickException("Swagger endpoint returned empty payload")

    with open(output, "w", encoding="utf-8") as f:
        json.dump(spec, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    path_count = len(spec.get("paths", {}))
    click.echo(f"OpenAPI spec written to {output} ({path_count} paths)")
