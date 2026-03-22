from __future__ import annotations

import json
import re
from pathlib import Path

SMOKE_REQUESTS = {
    "01 - Healthz",
    "02 - Register user (REST v2)",
    "03 - Login user (REST v2)",
    "04 - Login invalid credentials returns safe error",
    "05 - Me (REST v2)",
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
    "04 - GraphQL installment vs cash calculate (public)",
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
    assert "04 - GraphQL installment vs cash calculate (public)" in names
    assert "05 - GraphQL installment vs cash save (auth required)" in names


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
        ("GET", "/user/profile"),
        ("PUT", "/user/profile"),
        ("GET", "/user/profile/questionnaire"),
        ("POST", "/user/profile/questionnaire"),
        ("POST", "/transactions"),
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
        ("POST", "/simulations/{param}/goal"),
        ("POST", "/simulations/{param}/planned-expense"),
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
        "05 - GraphQL",
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
