from __future__ import annotations


def _load_openapi_paths(client) -> dict[str, dict[str, object]]:
    response = client.get("/docs/swagger/")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    paths = payload.get("paths")
    assert isinstance(paths, dict)
    return paths


def test_openapi_includes_critical_routes(client) -> None:
    paths = _load_openapi_paths(client)

    expected_paths = {
        "/auth/register",
        "/auth/login",
        "/auth/logout",
        "/auth/password/forgot",
        "/auth/password/reset",
        "/healthz",
        "/user/me",
        "/user/profile",
        "/transactions",
        "/transactions/list",
        "/transactions/summary",
        "/transactions/dashboard",
        "/transactions/expenses",
        "/transactions/due-range",
        "/transactions/deleted",
        "/transactions/{transaction_id}",
        "/transactions/{transaction_id}/force",
        "/transactions/restore/{transaction_id}",
        "/goals",
        "/goals/{goal_id}",
        "/goals/{goal_id}/plan",
        "/goals/simulate",
        "/wallet",
        "/wallet/{investment_id}",
        "/wallet/{investment_id}/history",
        "/wallet/{investment_id}/operations",
        "/wallet/{investment_id}/operations/{operation_id}",
        "/wallet/{investment_id}/operations/position",
        "/wallet/{investment_id}/operations/invested-amount",
        "/wallet/{investment_id}/operations/summary",
        "/wallet/{investment_id}/valuation",
        "/wallet/valuation",
        "/wallet/valuation/history",
    }

    missing_paths = sorted(expected_paths - set(paths))
    assert not missing_paths, f"OpenAPI missing documented paths: {missing_paths}"


def test_openapi_methods_match_main_routes(client) -> None:
    paths = _load_openapi_paths(client)

    expected_methods = {
        "/auth/register": {"post"},
        "/auth/login": {"post"},
        "/auth/logout": {"post"},
        "/auth/password/forgot": {"post"},
        "/auth/password/reset": {"post"},
        "/healthz": {"get"},
        "/user/me": {"get"},
        "/user/profile": {"get", "put"},
        "/transactions": {"post", "put", "delete"},
        "/transactions/{transaction_id}": {"put", "delete"},
        "/transactions/{transaction_id}/force": {"delete"},
        "/transactions/restore/{transaction_id}": {"patch"},
        "/transactions/due-range": {"get"},
        "/goals": {"get", "post"},
        "/goals/{goal_id}": {"get", "put", "delete"},
        "/goals/{goal_id}/plan": {"get"},
        "/goals/simulate": {"post"},
        "/wallet": {"get", "post"},
        "/wallet/{investment_id}": {"put", "delete"},
        "/wallet/{investment_id}/operations": {"get", "post"},
        "/wallet/{investment_id}/operations/{operation_id}": {"put", "delete"},
    }

    for path, methods in expected_methods.items():
        assert path in paths, f"Missing path in OpenAPI: {path}"
        documented_methods = set(paths[path].keys()) - {"options", "head"}
        assert methods.issubset(documented_methods), (
            f"Path {path} missing methods {sorted(methods - documented_methods)}. "
            f"Documented: {sorted(documented_methods)}"
        )
