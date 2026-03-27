#!/usr/bin/env python3
"""Client-side latency budget gate for critical API routes."""

from __future__ import annotations

import argparse
import json
import random
import string
import time
import urllib.error
import urllib.parse
import urllib.request
from math import ceil
from pathlib import Path
from typing import Any, cast

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]
CONFIG_FILE = (
    Path(__file__).resolve().parents[1] / "config" / "http_latency_budgets.json"
)


class LatencyBudgetError(RuntimeError):
    """Raised when the latency governance gate cannot pass."""


def _load_config(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    routes = payload.get("routes", [])
    if not isinstance(routes, list):
        raise LatencyBudgetError("Latency budget config must define a routes list")
    return [route for route in routes if isinstance(route, dict)]


def _nearest_rank_percentile(values: list[int], percentile: int) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    rank = max(1, ceil((percentile / 100) * len(ordered)))
    return ordered[rank - 1]


def _try_parse_json(body_text: str) -> JSONValue | None:
    if not body_text.strip():
        return None
    try:
        return cast(JSONValue, json.loads(body_text))
    except json.JSONDecodeError:
        return None


def _build_url(base_url: str, path: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise LatencyBudgetError(f"Invalid base URL: {base_url!r}")
    return f"{base_url.rstrip('/')}{path}"


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, JSONValue] | None = None,
    timeout: int = 15,
    headers: dict[str, str] | None = None,
) -> tuple[int, JSONValue | None, int]:
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    data: bytes | None = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    request = urllib.request.Request(
        url=url,
        data=data,
        headers=request_headers,
        method=method,
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body_text = response.read().decode("utf-8", errors="replace")
            duration_ms = int((time.perf_counter() - started) * 1000)
            return response.status, _try_parse_json(body_text), duration_ms
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        duration_ms = int((time.perf_counter() - started) * 1000)
        return int(exc.code), _try_parse_json(body_text), duration_ms
    except urllib.error.URLError as exc:
        raise LatencyBudgetError(f"Network error for {method} {url}: {exc}") from exc


def _random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=12))
    return f"latency-{suffix}@example.com"


def _register_user(base_url: str, *, password: str, timeout: int) -> tuple[str, str]:
    email = _random_email()
    status, body, _ = _request_json(
        method="POST",
        url=_build_url(base_url, "/auth/register"),
        payload={
            "name": "Latency Gate",
            "email": email,
            "password": password,
        },
        timeout=timeout,
        headers={"X-API-Contract": "v2"},
    )
    if status != 201:
        raise LatencyBudgetError(f"Register user expected 201, got {status}")
    if not isinstance(body, dict) or body.get("success") is not True:
        raise LatencyBudgetError(
            "Register user did not return canonical success payload"
        )
    return email, password


def _login_user(
    base_url: str, *, email: str, password: str, timeout: int
) -> tuple[str, int]:
    status, body, duration_ms = _request_json(
        method="POST",
        url=_build_url(base_url, "/auth/login"),
        payload={"email": email, "password": password},
        timeout=timeout,
        headers={"X-API-Contract": "v2"},
    )
    if status != 200:
        raise LatencyBudgetError(f"Login expected 200, got {status}")
    if not isinstance(body, dict):
        raise LatencyBudgetError("Login did not return a JSON object")
    data = body.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("token"), str):
        raise LatencyBudgetError("Login did not return an auth token")
    return str(data["token"]), duration_ms


def _measure_me(base_url: str, *, token: str, timeout: int) -> int:
    status, body, duration_ms = _request_json(
        method="GET",
        url=_build_url(base_url, "/user/me?page=1&limit=10"),
        timeout=timeout,
        headers={
            "Authorization": f"Bearer {token}",
            "X-API-Contract": "v2",
        },
    )
    if status != 200:
        raise LatencyBudgetError(f"GET /user/me expected 200, got {status}")
    if not isinstance(body, dict) or body.get("success") is not True:
        raise LatencyBudgetError(
            "GET /user/me did not return canonical success payload"
        )
    return duration_ms


def _measure_graphql_me(base_url: str, *, token: str, timeout: int) -> int:
    status, body, duration_ms = _request_json(
        method="POST",
        url=_build_url(base_url, "/graphql"),
        payload={"query": "query { me { id email name } }"},
        timeout=timeout,
        headers={"Authorization": f"Bearer {token}"},
    )
    if status != 200:
        raise LatencyBudgetError(f"GraphQL me expected 200, got {status}")
    if not isinstance(body, dict):
        raise LatencyBudgetError("GraphQL me did not return a JSON object")
    data = body.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("me"), dict):
        raise LatencyBudgetError("GraphQL me did not return expected payload")
    return duration_ms


def _measure_health(base_url: str, *, timeout: int) -> int:
    status, _, duration_ms = _request_json(
        method="GET",
        url=_build_url(base_url, "/healthz"),
        timeout=timeout,
    )
    if status != 200:
        raise LatencyBudgetError(f"GET /healthz expected 200, got {status}")
    return duration_ms


def _build_report(
    routes: list[dict[str, Any]], *, samples: int, base_url: str, timeout: int
) -> dict[str, Any]:
    password = "PerfGate123!"
    email, _ = _register_user(base_url, password=password, timeout=timeout)
    token, first_login_ms = _login_user(
        base_url,
        email=email,
        password=password,
        timeout=timeout,
    )

    route_samples: dict[str, list[int]] = {str(route["name"]): [] for route in routes}
    route_samples["auth.login"].append(first_login_ms)

    for _ in range(max(samples - 1, 0)):
        _, login_ms = _login_user(
            base_url,
            email=email,
            password=password,
            timeout=timeout,
        )
        route_samples["auth.login"].append(login_ms)

    for _ in range(samples):
        route_samples["health.healthz"].append(
            _measure_health(base_url, timeout=timeout)
        )
        route_samples["user.me"].append(
            _measure_me(base_url, token=token, timeout=timeout)
        )
        route_samples["graphql.me"].append(
            _measure_graphql_me(base_url, token=token, timeout=timeout)
        )

    results: dict[str, Any] = {}
    all_within_budget = True
    for route in routes:
        name = str(route["name"])
        durations = route_samples[name]
        budget_ms = int(route["budget_ms"])
        p95_ms = _nearest_rank_percentile(durations, 95)
        within_budget = p95_ms <= budget_ms
        all_within_budget = all_within_budget and within_budget
        results[name] = {
            "method": str(route["method"]),
            "path": str(route["path"]),
            "scenario": str(route["scenario"]),
            "budget_ms": budget_ms,
            "samples": len(durations),
            "p50_ms": _nearest_rank_percentile(durations, 50),
            "p95_ms": p95_ms,
            "max_ms": max(durations),
            "avg_ms": round(sum(durations) / len(durations), 2),
            "within_budget": within_budget,
        }

    return {
        "component": "http_latency_budget_governance",
        "samples_per_route": samples,
        "all_within_budget": all_within_budget,
        "routes": results,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Client-side latency budget governance for critical API routes."
    )
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--samples", type=int, default=3)
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--config", default=str(CONFIG_FILE))
    parser.add_argument(
        "--output",
        default="reports/performance/http-latency-budget.json",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    routes = _load_config(Path(args.config))
    payload = _build_report(
        routes,
        samples=max(1, int(args.samples)),
        base_url=str(args.base_url),
        timeout=int(args.timeout),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    print(json.dumps(payload, sort_keys=True))
    if not payload["all_within_budget"]:
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
