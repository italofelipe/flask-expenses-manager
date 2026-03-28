from __future__ import annotations


def _load_openapi_paths(client) -> dict[str, dict[str, object]]:
    response = client.get("/docs/swagger/")
    assert response.status_code == 200
    payload = response.get_json()
    assert isinstance(payload, dict)
    paths = payload.get("paths")
    assert isinstance(paths, dict)
    return paths


def _operation(
    paths: dict[str, dict[str, object]],
    path: str,
    method: str,
) -> dict[str, object]:
    operation = paths[path][method]
    assert isinstance(operation, dict)
    return operation


def test_openapi_docs_cover_mvp1_core_examples_and_headers(client) -> None:
    paths = _load_openapi_paths(client)

    login = _operation(paths, "/auth/login", "post")
    request_body = login["requestBody"]
    assert isinstance(request_body, dict)
    request_content = request_body["content"]
    assert isinstance(request_content, dict)
    login_json = request_content["application/json"]
    assert isinstance(login_json, dict)
    assert "example" in login_json
    responses = login["responses"]
    assert isinstance(responses, dict)
    assert "example" in responses["200"]["content"]["application/json"]
    assert "example" in responses["401"]["content"]["application/json"]
    login_headers = responses["200"]["headers"]
    assert "Deprecation" in login_headers
    assert "X-Auraxis-Successor-Field" in login_headers

    user_me = _operation(paths, "/user/me", "get")
    params = user_me["parameters"]
    assert isinstance(params, list)
    assert any(param.get("name") == "X-API-Contract" for param in params)
    assert "example" in user_me["responses"]["200"]["content"]["application/json"]

    bootstrap = _operation(paths, "/user/bootstrap", "get")
    assert "example" in bootstrap["responses"]["200"]["content"]["application/json"]
    bootstrap_example = bootstrap["responses"]["200"]["content"]["application/json"][
        "example"
    ]
    assert bootstrap_example["data"]["wallet"]["limit"] >= 1
    assert "returned_items" in bootstrap_example["data"]["wallet"]
    assert "has_more" in bootstrap_example["data"]["wallet"]

    dashboard = _operation(paths, "/dashboard/overview", "get")
    assert "example" in dashboard["responses"]["200"]["content"]["application/json"]

    transactions = _operation(paths, "/transactions", "get")
    assert "example" in transactions["responses"]["200"]["content"]["application/json"]

    transaction_create = _operation(paths, "/transactions", "post")
    assert "example" in transaction_create["requestBody"]["content"]["application/json"]

    transaction_detail = _operation(paths, "/transactions/{transaction_id}", "get")
    assert (
        "example"
        in transaction_detail["responses"]["200"]["content"]["application/json"]
    )

    transaction_patch = _operation(paths, "/transactions/{transaction_id}", "patch")
    assert "example" in transaction_patch["requestBody"]["content"]["application/json"]

    transaction_put = _operation(paths, "/transactions/{transaction_id}", "put")
    put_headers = transaction_put["responses"]["200"]["headers"]
    assert "Deprecation" in put_headers
    assert "X-Auraxis-Successor-Method" in put_headers

    goal_patch = _operation(paths, "/goals/{goal_id}", "patch")
    assert "description" in goal_patch
    goal_put = _operation(paths, "/goals/{goal_id}", "put")
    goal_put_headers = goal_put["responses"]["200"]["headers"]
    assert "Deprecation" in goal_put_headers
    assert goal_put_headers["X-Auraxis-Successor-Method"]["example"] == "PATCH"

    simulation_canonical = _operation(paths, "/simulations/installment-vs-cash", "post")
    assert "description" in simulation_canonical
    simulation_compat = _operation(
        paths, "/simulations/installment-vs-cash/save", "post"
    )
    simulation_headers = simulation_compat["responses"]["201"]["headers"]
    assert "Deprecation" in simulation_headers
    assert simulation_headers["X-Auraxis-Successor-Endpoint"]["example"] == (
        "/simulations/installment-vs-cash"
    )

    wallet_detail = _operation(paths, "/wallet/{investment_id}", "get")
    wallet_params = wallet_detail["parameters"]
    assert isinstance(wallet_params, list)
    assert any(param.get("name") == "investment_id" for param in wallet_params)

    wallet_patch = _operation(paths, "/wallet/{investment_id}", "patch")
    assert "description" in wallet_patch
    wallet_put = _operation(paths, "/wallet/{investment_id}", "put")
    wallet_put_headers = wallet_put["responses"]["200"]["headers"]
    assert "Deprecation" in wallet_put_headers
    assert wallet_put_headers["X-Auraxis-Successor-Method"]["example"] == "PATCH"

    wallet_history = _operation(paths, "/wallet/valuation/history", "get")
    wallet_history_params = wallet_history["parameters"]
    assert isinstance(wallet_history_params, list)
    assert any(param.get("name") == "start_date" for param in wallet_history_params)
    assert any(param.get("name") == "end_date" for param in wallet_history_params)
    assert any(param.get("name") == "startDate" for param in wallet_history_params)
    assert any(param.get("name") == "finalDate" for param in wallet_history_params)

    transaction_dashboard = _operation(paths, "/transactions/dashboard", "get")
    dashboard_headers = transaction_dashboard["responses"]["200"]["headers"]
    assert "Deprecation" in dashboard_headers
    assert dashboard_headers["X-Auraxis-Successor-Endpoint"]["example"] == (
        "/dashboard/overview"
    )
