"""POSTMAN-01 — Tests for ``flask openapi-export`` CLI command.

Verifies that the command:
1. Produces a valid OpenAPI 3.0 JSON file.
2. Is deterministic (two runs → identical output).
3. Contains expected paths.
"""

from __future__ import annotations

import json
from pathlib import Path


def test_openapi_export_produces_valid_json(app, tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    runner = app.test_cli_runner()

    result = runner.invoke(args=["openapi-export", "--output", str(output)])

    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert output.exists()

    spec = json.loads(output.read_text(encoding="utf-8"))
    assert spec.get("openapi", "").startswith("3.0")
    assert "paths" in spec
    assert len(spec["paths"]) > 0


def test_openapi_export_is_deterministic(app, tmp_path: Path) -> None:
    """Two consecutive runs must produce byte-identical output."""
    out1 = tmp_path / "run1.json"
    out2 = tmp_path / "run2.json"
    runner = app.test_cli_runner()

    runner.invoke(args=["openapi-export", "--output", str(out1)])
    runner.invoke(args=["openapi-export", "--output", str(out2)])

    assert out1.read_bytes() == out2.read_bytes(), (
        "OpenAPI export is not deterministic — two runs produced different output"
    )


def test_openapi_export_contains_known_paths(app, tmp_path: Path) -> None:
    output = tmp_path / "openapi.json"
    runner = app.test_cli_runner()
    runner.invoke(args=["openapi-export", "--output", str(output)])

    spec = json.loads(output.read_text(encoding="utf-8"))
    paths = set(spec.get("paths", {}).keys())

    # At minimum, health and auth endpoints must be present
    assert any("/health" in p for p in paths), f"Missing /health in paths: {paths}"
    assert any("/auth" in p for p in paths), f"Missing /auth in paths: {paths}"


def test_openapi_export_default_output(app, tmp_path: Path, monkeypatch) -> None:
    """Without --output, defaults to openapi.json in cwd."""
    monkeypatch.chdir(tmp_path)
    runner = app.test_cli_runner()

    result = runner.invoke(args=["openapi-export"])

    assert result.exit_code == 0
    default_output = tmp_path / "openapi.json"
    assert default_output.exists()
