from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_module():
    module_path = (
        Path(__file__).resolve().parents[2] / "scripts" / "http_latency_budget_gate.py"
    )
    spec = importlib.util.spec_from_file_location(
        "http_latency_budget_gate", module_path
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_load_config_reads_route_entries(tmp_path: Path) -> None:
    module = _load_module()
    config_path = tmp_path / "budgets.json"
    config_path.write_text(
        json.dumps(
            {
                "version": 1,
                "routes": [
                    {
                        "name": "health.healthz",
                        "method": "GET",
                        "path": "/healthz",
                        "budget_ms": 100,
                        "scenario": "healthz",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    routes = module._load_config(config_path)

    assert routes[0]["name"] == "health.healthz"
    assert routes[0]["budget_ms"] == 100


def test_build_report_marks_routes_within_budget(monkeypatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_register_user",
        lambda *args, **kwargs: ("user@example.com", "PerfGate123!"),
    )
    login_samples = iter([120, 140, 160])
    monkeypatch.setattr(
        module,
        "_login_user",
        lambda *args, **kwargs: ("token-123", next(login_samples)),
    )
    health_samples = iter([20, 25, 30])
    monkeypatch.setattr(
        module,
        "_measure_health",
        lambda *args, **kwargs: next(health_samples),
    )
    me_samples = iter([80, 90, 100])
    monkeypatch.setattr(
        module,
        "_measure_me",
        lambda *args, **kwargs: next(me_samples),
    )
    graphql_samples = iter([200, 220, 250])
    monkeypatch.setattr(
        module,
        "_measure_graphql_me",
        lambda *args, **kwargs: next(graphql_samples),
    )

    payload = module._build_report(
        module._load_config(Path("config/http_latency_budgets.json")),
        samples=3,
        base_url="http://localhost:3333",
        timeout=15,
    )

    assert payload["all_within_budget"] is True
    assert payload["routes"]["auth.login"]["p95_ms"] == 160
    assert payload["routes"]["user.me"]["within_budget"] is True
    assert payload["routes"]["graphql.me"]["samples"] == 3


def test_build_report_fails_budget_when_p95_regresses(monkeypatch) -> None:
    module = _load_module()

    monkeypatch.setattr(
        module,
        "_register_user",
        lambda *args, **kwargs: ("user@example.com", "PerfGate123!"),
    )
    login_samples = iter([120, 140, 350])
    monkeypatch.setattr(
        module,
        "_login_user",
        lambda *args, **kwargs: ("token-123", next(login_samples)),
    )
    monkeypatch.setattr(module, "_measure_health", lambda *args, **kwargs: 20)
    monkeypatch.setattr(module, "_measure_me", lambda *args, **kwargs: 100)
    monkeypatch.setattr(module, "_measure_graphql_me", lambda *args, **kwargs: 200)

    payload = module._build_report(
        module._load_config(Path("config/http_latency_budgets.json")),
        samples=3,
        base_url="http://localhost:3333",
        timeout=15,
    )

    assert payload["all_within_budget"] is False
    assert payload["routes"]["auth.login"]["within_budget"] is False
