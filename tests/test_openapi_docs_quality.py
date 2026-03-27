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

    user_me = _operation(paths, "/user/me", "get")
    params = user_me["parameters"]
    assert isinstance(params, list)
    assert any(param.get("name") == "X-API-Contract" for param in params)
    assert "example" in user_me["responses"]["200"]["content"]["application/json"]

    bootstrap = _operation(paths, "/user/bootstrap", "get")
    assert "example" in bootstrap["responses"]["200"]["content"]["application/json"]

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

    transaction_dashboard = _operation(paths, "/transactions/dashboard", "get")
    dashboard_headers = transaction_dashboard["responses"]["200"]["headers"]
    assert "Deprecation" in dashboard_headers
    assert dashboard_headers["X-Auraxis-Successor-Endpoint"]["example"] == (
        "/dashboard/overview"
    )
