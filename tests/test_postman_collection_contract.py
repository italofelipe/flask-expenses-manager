from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SMOKE_REQUESTS = {
    "01 - Healthz",
    "02 - Register user (REST v2)",
    "03 - Login user (REST v2)",
    "04 - Login invalid credentials returns safe error",
    "05 - Me (REST v2)",
    "06 - User bootstrap (REST v2)",
    "01 - Create transaction (REST v2)",
    "04 - List active transactions (REST v2)",
    "05 - Transaction summary by month (REST v2)",
    "01 - Create goal (REST v2)",
    "02 - List goals (REST v2)",
    "05 - Goal simulate (REST v2)",
    "01 - Create wallet investment (REST v2)",
    "02 - List wallet investments (REST v2)",
    "08 - Create wallet operation (REST v2)",
    "10 - Wallet operation summary (REST v2)",
    "01 - Installment vs cash calculate (REST public)",
    "02 - Installment vs cash save (REST auth required)",
    "03 - Simulation goal bridge without entitlement returns 403",
    "02 - GraphQL login invalid credentials (safe error)",
    "03 - GraphQL me query (auth required)",
    "06 - GraphQL installment vs cash calculate (public)",
    "01 - List alert preferences (REST v2)",
    "01 - Get my subscription (REST v2)",
    "01 - List entitlements (REST v2)",
    "01 - List shared entries by me (REST v2)",
    "01 - CSV upload preview (REST v2)",
}
PRIVILEGED_REQUESTS = {
    "01 - Healthz",
    "02 - Register user (REST v2)",
    "03 - Login user (REST v2)",
    "05 - Me (REST v2)",
    "06 - User bootstrap (REST v2)",
    "01 - Installment vs cash calculate (REST public)",
    "02 - Installment vs cash save (REST auth required)",
    "03 - Simulation goal bridge without entitlement returns 403",
    "04 - Grant advanced simulations entitlement (optional admin)",
    "05 - Save advanced simulation for success bridges (optional admin)",
    "06 - Simulation goal bridge success (optional admin)",
    "07 - Save fee simulation for planned expense bridge (optional admin)",
    "08 - Simulation planned expense bridge success (optional admin)",
    "09 - Revoke advanced simulations entitlement (optional admin)",
}


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
        if segment.startswith("{{") and segment.endswith("}}"):
            segments.append("{param}")
            continue
        if re.fullmatch(r"\{[^}]+\}", segment):
            segments.append("{param}")
            continue
        segments.append(segment)
    return "/" + "/".join(segments)


def test_postman_collection_covers_installment_vs_cash_rest_and_graphql() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = {str(item.get("name")) for item in items}

    assert "01 - Installment vs cash calculate (REST public)" in names
    assert "02 - Installment vs cash save (REST auth required)" in names
    assert "06 - GraphQL installment vs cash calculate (public)" in names
    assert "07 - GraphQL installment vs cash save (auth required)" in names


def test_postman_collection_covers_canonical_graphql_operations() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = {str(item.get("name")) for item in items}

    expected = {
        "01 - GraphQL empty query (validation error)",
        "02 - GraphQL login invalid credentials (safe error)",
        "03 - GraphQL me query (auth required)",
        "04 - GraphQL forgot password stays neutral",
        "05 - GraphQL reset password invalid token is public validation error",
        "06 - GraphQL installment vs cash calculate (public)",
        "07 - GraphQL installment vs cash save (auth required)",
        "08 - GraphQL transaction dashboard seed (auth required)",
        "09 - GraphQL transaction summary and dashboard (auth required)",
        "10 - GraphQL wallet create (auth required)",
        "11 - GraphQL wallet list and valuation (auth required)",
        "12 - GraphQL logout mutation (auth required)",
    }

    missing = sorted(expected - names)
    assert not missing, (
        f"Postman collection missing canonical GraphQL coverage: {missing}"
    )


def test_postman_collection_covers_critical_rest_routes() -> None:
    items = _flatten_request_items(_load_postman_items())
    covered = {
        (
            str(item["request"]["method"]).upper(),
            _normalize_path(str(item["request"]["url"]["raw"])),
        )
        for item in items
    }

    expected = {
        ("GET", "/healthz"),
        ("POST", "/auth/register"),
        ("POST", "/auth/login"),
        ("POST", "/auth/logout"),
        ("POST", "/auth/password/forgot"),
        ("POST", "/auth/password/reset"),
        ("GET", "/user/me"),
        ("GET", "/user/bootstrap"),
        ("GET", "/user/profile"),
        ("PUT", "/user/profile"),
        ("GET", "/user/profile/questionnaire"),
        ("POST", "/user/profile/questionnaire"),
        ("POST", "/user/simulate-salary-increase"),
        ("GET", "/transactions"),
        ("POST", "/transactions"),
        ("GET", "/transactions/{param}"),
        ("PATCH", "/transactions/{param}"),
        ("PUT", "/transactions/{param}"),
        ("DELETE", "/transactions/{param}"),
        ("GET", "/transactions/list"),
        ("GET", "/transactions/summary"),
        ("GET", "/transactions/dashboard"),
        ("GET", "/transactions/expenses"),
        ("GET", "/transactions/due-range"),
        ("GET", "/transactions/deleted"),
        ("PATCH", "/transactions/restore/{param}"),
        ("DELETE", "/transactions/{param}/force"),
        ("GET", "/goals"),
        ("POST", "/goals"),
        ("GET", "/goals/{param}"),
        ("PUT", "/goals/{param}"),
        ("PATCH", "/goals/{param}"),
        ("DELETE", "/goals/{param}"),
        ("GET", "/goals/{param}/plan"),
        ("POST", "/goals/simulate"),
        ("GET", "/wallet"),
        ("POST", "/wallet"),
        ("PUT", "/wallet/{param}"),
        ("DELETE", "/wallet/{param}"),
        ("GET", "/wallet/{param}/history"),
        ("GET", "/wallet/valuation"),
        ("GET", "/wallet/valuation/history"),
        ("GET", "/wallet/{param}/valuation"),
        ("GET", "/wallet/{param}/operations"),
        ("POST", "/wallet/{param}/operations"),
        ("PUT", "/wallet/{param}/operations/{param}"),
        ("DELETE", "/wallet/{param}/operations/{param}"),
        ("GET", "/wallet/{param}/operations/summary"),
        ("GET", "/wallet/{param}/operations/position"),
        ("GET", "/wallet/{param}/operations/invested-amount"),
        ("POST", "/simulations/installment-vs-cash/calculate"),
        ("POST", "/simulations/installment-vs-cash/save"),
        ("GET", "/simulations"),
        ("POST", "/simulations"),
        ("GET", "/simulations/{param}"),
        ("DELETE", "/simulations/{param}"),
        ("POST", "/simulations/{param}/goal"),
        ("POST", "/simulations/{param}/planned-expense"),
        ("GET", "/alerts/preferences"),
        ("PUT", "/alerts/preferences/{param}"),
        ("GET", "/alerts"),
        ("POST", "/alerts/{param}/read"),
        ("DELETE", "/alerts/{param}"),
        ("GET", "/subscriptions/me"),
        ("POST", "/subscriptions/checkout"),
        ("POST", "/subscriptions/cancel"),
        ("POST", "/subscriptions/webhook"),
        ("GET", "/entitlements"),
        ("GET", "/entitlements/check"),
        ("POST", "/entitlements/admin"),
        ("DELETE", "/entitlements/admin/{param}"),
        ("POST", "/shared-entries"),
        ("GET", "/shared-entries/by-me"),
        ("GET", "/shared-entries/with-me"),
        ("DELETE", "/shared-entries/{param}"),
        ("GET", "/shared-entries/invitations"),
        ("POST", "/shared-entries/invitations"),
        ("POST", "/shared-entries/invitations/{param}/accept"),
        ("DELETE", "/shared-entries/invitations/{param}"),
        ("POST", "/fiscal/csv/upload"),
        ("POST", "/fiscal/csv/confirm"),
        ("GET", "/fiscal/receivables"),
        ("POST", "/fiscal/receivables"),
        ("PATCH", "/fiscal/receivables/{param}/receive"),
        ("DELETE", "/fiscal/receivables/{param}"),
        ("GET", "/fiscal/receivables/summary"),
        ("GET", "/fiscal/fiscal-documents"),
        ("POST", "/fiscal/fiscal-documents"),
    }

    missing = sorted(expected - covered)
    assert not missing, f"Postman collection missing critical REST coverage: {missing}"


def test_postman_collection_uses_domain_folders() -> None:
    top_level = _load_postman_items()
    folder_names = [str(item.get("name")) for item in top_level]
    assert folder_names == [
        "00 - Auth and User Bootstrap",
        "01 - Transactions",
        "02 - Goals",
        "03 - Wallet",
        "04 - Simulations",
        "05 - Alerts",
        "06 - Subscriptions and Entitlements",
        "07 - Shared Entries",
        "08 - Fiscal",
        "09 - GraphQL",
    ]


def test_postman_collection_request_names_are_unique() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = [str(item.get("name")) for item in items]
    assert len(names) == len(set(names)), "Postman request names must stay unique"


def test_postman_collection_smoke_profile_covers_known_requests() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = {str(item.get("name")) for item in items}
    missing = sorted(SMOKE_REQUESTS - names)
    assert not missing, f"Smoke profile references unknown requests: {missing}"


def test_postman_collection_privileged_profile_covers_known_requests() -> None:
    items = _flatten_request_items(_load_postman_items())
    names = {str(item.get("name")) for item in items}
    missing = sorted(PRIVILEGED_REQUESTS - names)
    assert not missing, f"Privileged profile references unknown requests: {missing}"


def test_postman_collection_smoke_profile_excludes_privileged_only_requests() -> None:
    privileged_only = {
        "04 - Grant advanced simulations entitlement (optional admin)",
        "05 - Save advanced simulation for success bridges (optional admin)",
        "06 - Simulation goal bridge success (optional admin)",
        "07 - Save fee simulation for planned expense bridge (optional admin)",
        "08 - Simulation planned expense bridge success (optional admin)",
        "09 - Revoke advanced simulations entitlement (optional admin)",
    }
    overlap = sorted(SMOKE_REQUESTS & privileged_only)
    assert not overlap, f"Smoke profile must not include privileged requests: {overlap}"


def test_postman_collection_covers_registered_rest_routes(app: Any) -> None:
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
                if route_key not in covered:
                    missing.append((method, normalized_rule, rule.endpoint))

    assert not missing, f"Postman collection missing registered REST routes: {missing}"
