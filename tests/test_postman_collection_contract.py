"""Contract tests for the OpenAPI-generated Postman collection.

These tests verify that ``scripts/openapi_to_postman.py`` produces a
collection that covers the routes exposed in ``openapi.json``, uses
deterministic folder names, and has unique request names.

Routes NOT in the OpenAPI spec (alerts, subscriptions, shared-entries,
fiscal, GraphQL, tags/accounts/credit-cards) are tracked in
``OPENAPI_GAPS`` and excluded from coverage checks until they are
registered with apispec.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def _load_postman_items() -> list[dict[str, object]]:
    collection_path = (
        Path(__file__).resolve().parents[1]
        / "api-tests"
        / "postman"
        / "auraxis.postman_collection.json"
    )
    payload = json.loads(collection_path.read_text())
    items = payload.get("item")
    assert isinstance(items, list)
    return items


def _flatten_request_items(items: list[dict[str, object]]) -> list[dict[str, object]]:
    flattened: list[dict[str, object]] = []
    for item in items:
        nested = item.get("item")
        if isinstance(nested, list):
            flattened.extend(_flatten_request_items(nested))
            continue
        flattened.append(item)
    return flattened


def _normalize_path(raw_url: str) -> str:
    path = raw_url.split("{{baseUrl}}", 1)[1].split("?", 1)[0]
    segments = []
    for segment in path.split("/"):
        if not segment:
            continue
        if segment.startswith(":"):
            segments.append("{param}")
            continue
        if segment.startswith("{{") and segment.endswith("}}"):
            segments.append("{param}")
            continue
        if re.fullmatch(r"\{[^}]+\}", segment):
            segments.append("{param}")
            continue
        segments.append(segment)
    return "/" + "/".join(segments)


# Routes registered in Flask but not yet in the OpenAPI spec.
# Each entry is (METHOD, normalized_path). These are excluded from
# coverage checks until apispec registration is added.
OPENAPI_GAPS: set[tuple[str, str]] = {
    # Alerts
    ("GET", "/alerts"),
    ("GET", "/alerts/preferences"),
    ("PUT", "/alerts/preferences/{param}"),
    ("POST", "/alerts/{param}/read"),
    ("DELETE", "/alerts/{param}"),
    # Subscriptions
    ("GET", "/subscriptions/plans"),
    ("GET", "/subscriptions/me"),
    ("POST", "/subscriptions/checkout"),
    ("POST", "/subscriptions/cancel"),
    ("POST", "/subscriptions/webhook"),
    # Shared entries
    ("POST", "/shared-entries"),
    ("GET", "/shared-entries/by-me"),
    ("GET", "/shared-entries/with-me"),
    ("DELETE", "/shared-entries/{param}"),
    ("GET", "/shared-entries/invitations"),
    ("POST", "/shared-entries/invitations"),
    ("POST", "/shared-entries/invitations/{param}/accept"),
    ("DELETE", "/shared-entries/invitations/{param}"),
    # Fiscal
    ("POST", "/fiscal/csv/upload"),
    ("POST", "/fiscal/csv/confirm"),
    ("GET", "/fiscal/receivables"),
    ("POST", "/fiscal/receivables"),
    ("PATCH", "/fiscal/receivables/{param}/receive"),
    ("DELETE", "/fiscal/receivables/{param}"),
    ("GET", "/fiscal/receivables/summary"),
    ("GET", "/fiscal/fiscal-documents"),
    ("POST", "/fiscal/fiscal-documents"),
    # Tags, accounts, credit cards
    ("GET", "/tags"),
    ("POST", "/tags"),
    ("GET", "/tags/{param}"),
    ("PATCH", "/tags/{param}"),
    ("DELETE", "/tags/{param}"),
    ("GET", "/accounts"),
    ("POST", "/accounts"),
    ("GET", "/accounts/{param}"),
    ("PATCH", "/accounts/{param}"),
    ("DELETE", "/accounts/{param}"),
    ("GET", "/credit-cards"),
    ("POST", "/credit-cards"),
    ("GET", "/credit-cards/{param}"),
    ("PATCH", "/credit-cards/{param}"),
    ("DELETE", "/credit-cards/{param}"),
    # GraphQL
    ("GET", "/graphql"),
    ("POST", "/graphql"),
    # Reminders CLI-only (no REST route)
    # Auth email routes (confirm/resend have REST but via different path convention)
    # Recurrence
    ("GET", "/recurrences"),
    ("POST", "/recurrences"),
    ("GET", "/recurrences/{param}"),
    ("PATCH", "/recurrences/{param}"),
    ("DELETE", "/recurrences/{param}"),
    ("POST", "/recurrences/{param}/execute"),
    # Webhook events
    ("GET", "/webhook-events"),
    ("POST", "/webhook-events"),
    ("GET", "/webhook-events/{param}"),
    ("PATCH", "/webhook-events/{param}"),
    ("DELETE", "/webhook-events/{param}"),
    # J-task routes (MVP2)
    ("GET", "/j-tasks"),
    ("POST", "/j-tasks"),
    ("GET", "/j-tasks/{param}"),
    ("PATCH", "/j-tasks/{param}"),
    ("DELETE", "/j-tasks/{param}"),
    ("POST", "/j-tasks/{param}/execute"),
    # PUT variants (some resources expose PUT alongside PATCH)
    ("PUT", "/accounts/{param}"),
    ("PUT", "/credit-cards/{param}"),
    ("PUT", "/tags/{param}"),
    # Admin feature flags
    ("GET", "/admin/feature-flags"),
    ("POST", "/admin/feature-flags"),
    ("GET", "/admin/feature-flags/{param}"),
    ("DELETE", "/admin/feature-flags/{param}"),
    # Bank statements
    ("POST", "/bank-statements/preview"),
    ("POST", "/bank-statements/confirm"),
}


def test_postman_collection_uses_domain_folders() -> None:
    """Verify folder structure matches the OpenAPI tag mapping."""
    top_level = _load_postman_items()
    folder_names = [str(item.get("name")) for item in top_level]
    expected = [
        "00 - Health",
        "01 - Auth",
        "02 - User",
        "03 - Transactions",
        "04 - Budgets",
        "05 - Goals",
        "06 - Wallet",
        "07 - Simulations",
        "08 - Entitlements",
    ]
    assert folder_names == expected


def test_postman_collection_request_names_are_unique() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = [str(item.get("name")) for item in items]
    assert len(names) == len(set(names)), "Postman request names must stay unique"


def test_postman_collection_covers_openapi_paths() -> None:
    """Every path in openapi.json must have a corresponding Postman request."""
    openapi_path = Path(__file__).resolve().parents[1] / "openapi.json"
    spec = json.loads(openapi_path.read_text())
    covered = {
        (
            str(item["request"]["method"]).upper(),
            _normalize_path(str(item["request"]["url"]["raw"])),
        )
        for item in _flatten_request_items(_load_postman_items())
    }

    missing = []
    for path, methods in spec.get("paths", {}).items():
        for method in methods:
            if method.upper() == "OPTIONS":
                continue
            if not isinstance(methods[method], dict):
                continue
            normalized = re.sub(r"\{[^}]+\}", "{param}", path)
            key = (method.upper(), normalized)
            if key not in covered:
                missing.append(key)

    assert not missing, f"Postman collection missing OpenAPI paths: {sorted(missing)}"


def test_postman_collection_covers_registered_rest_routes(app: Any) -> None:
    """Check coverage of registered Flask routes, excluding known OpenAPI gaps."""
    covered = {
        (
            str(item["request"]["method"]).upper(),
            _normalize_path(str(item["request"]["url"]["raw"])),
        )
        for item in _flatten_request_items(_load_postman_items())
    }
    missing: list[tuple[str, str, str]] = []

    with app.app_context():
        for rule in sorted(
            app.url_map.iter_rules(),
            key=lambda r: (r.rule, sorted(r.methods)),
        ):
            if rule.endpoint == "static" or rule.endpoint.startswith("flask-apispec."):
                continue
            if rule.rule.startswith("/docs") or rule.rule.startswith("/swagger"):
                continue
            normalized_rule = re.sub(r"<(?:[^:>]+:)?[^>]+>", "{param}", rule.rule)
            for method in sorted(
                m for m in rule.methods if m not in {"HEAD", "OPTIONS"}
            ):
                route_key = (method, normalized_rule)
                if route_key in OPENAPI_GAPS:
                    continue
                if route_key not in covered:
                    missing.append((method, normalized_rule, rule.endpoint))

    assert not missing, f"Postman collection missing registered REST routes: {missing}"


def test_postman_collection_has_auth_headers_for_protected_routes() -> None:
    """Protected endpoints must include Authorization header."""
    public_prefixes = {
        "/healthz",
        "/readiness",
        "/ops/",
        "/auth/login",
        "/auth/register",
        "/auth/password/",
        "/auth/email/",
        "/simulations/installment-vs-cash/calculate",
    }
    items = _flatten_request_items(_load_postman_items())
    missing_auth = []
    for item in items:
        request = item.get("request", {})
        raw_url = str(request.get("url", {}).get("raw", ""))
        path = raw_url.split("{{baseUrl}}", 1)[-1].split("?")[0]
        if any(path.startswith(p) for p in public_prefixes):
            continue
        headers = request.get("header", [])
        has_auth = any(h.get("key") == "Authorization" for h in headers)
        if not has_auth:
            missing_auth.append(item.get("name"))
    assert not missing_auth, (
        f"Protected routes missing Authorization header: {missing_auth}"
    )
