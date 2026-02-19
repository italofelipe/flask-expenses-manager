#!/usr/bin/env python3
"""HTTP smoke checks for REST + GraphQL after deploy.

Goal
- Provide fast, deterministic post-deploy confidence checks for public endpoints.
- Fail with actionable output without leaking secrets.
"""

from __future__ import annotations

import argparse
import json
import random
import string
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class HttpResult:
    status: int
    body_text: str
    body_json: Any | None


class SmokeCheckError(RuntimeError):
    """Raised when a smoke check cannot pass safely."""


def _try_parse_json(body_text: str) -> Any | None:
    if not body_text.strip():
        return None
    try:
        return json.loads(body_text)
    except json.JSONDecodeError:
        return None


def _result_from_status(status: int, body_text: str) -> HttpResult:
    return HttpResult(
        status=status, body_text=body_text, body_json=_try_parse_json(body_text)
    )


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 15,
    headers: dict[str, str] | None = None,
) -> HttpResult:
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
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body_text = response.read().decode("utf-8", errors="replace")
            return _result_from_status(response.status, body_text)
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        return _result_from_status(exc.code, body_text)
    except urllib.error.URLError as exc:
        raise SmokeCheckError(f"Network error for {method} {url}: {exc}") from exc


def _build_url(base_url: str, path: str) -> str:
    parsed = urllib.parse.urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise SmokeCheckError(f"Invalid base URL: {base_url!r}")
    base = base_url.rstrip("/")
    return f"{base}{path}"


def _check_health(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/healthz")
    result = _request_json(method="GET", url=url, timeout=timeout)
    if result.status != 200:
        raise SmokeCheckError(f"REST /healthz expected 200, got {result.status}.")
    print(f"[smoke] PASS rest-health status={result.status} url={url}")


def _check_graphql_empty_query(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/graphql")
    result = _request_json(
        method="POST",
        url=url,
        payload={"query": "   "},
        timeout=timeout,
    )
    if result.status != 400:
        raise SmokeCheckError(
            f"GraphQL empty query expected HTTP 400, got {result.status}."
        )
    first_error = {}
    if isinstance(result.body_json, dict):
        errors = result.body_json.get("errors")
        if isinstance(errors, list) and errors:
            first_error = errors[0] if isinstance(errors[0], dict) else {}
    extensions = first_error.get("extensions", {})
    code = extensions.get("code") if isinstance(extensions, dict) else None
    if code != "VALIDATION_ERROR":
        raise SmokeCheckError(
            "GraphQL empty query expected extensions.code=VALIDATION_ERROR, "
            f"got {code!r}."
        )
    print(f"[smoke] PASS graphql-empty-query status={result.status} code={code}")


def _random_email() -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    return f"smoke-{suffix}@example.com"


def _check_rest_invalid_login(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/auth/login")
    result = _request_json(
        method="POST",
        url=url,
        payload={"email": _random_email(), "password": "invalid-password"},
        timeout=timeout,
        headers={"X-API-Contract": "v2"},
    )
    if result.status >= 500:
        raise SmokeCheckError(
            f"REST invalid login must not fail with 5xx (got {result.status})."
        )
    accepted_status = {400, 401, 429, 503}
    if result.status not in accepted_status:
        raise SmokeCheckError(
            f"REST invalid login unexpected status {result.status}. "
            f"Accepted: {sorted(accepted_status)}."
        )
    print(f"[smoke] PASS rest-invalid-login status={result.status}")


def _check_graphql_invalid_login(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/graphql")
    mutation = (
        "mutation Login($email: String, $password: String!) { "
        "login(email: $email, password: $password) { token message } }"
    )
    result = _request_json(
        method="POST",
        url=url,
        payload={
            "query": mutation,
            "variables": {"email": _random_email(), "password": "invalid-password"},
        },
        timeout=timeout,
    )
    if result.status != 200:
        raise SmokeCheckError(
            f"GraphQL invalid login transport expected HTTP 200, got {result.status}."
        )
    first_error = {}
    if isinstance(result.body_json, dict):
        errors = result.body_json.get("errors")
        if isinstance(errors, list) and errors:
            first_error = errors[0] if isinstance(errors[0], dict) else {}
    extensions = first_error.get("extensions", {})
    code = extensions.get("code") if isinstance(extensions, dict) else None
    if not code:
        raise SmokeCheckError(
            "GraphQL invalid login should return a public error code."
        )
    if code == "INTERNAL_ERROR":
        raise SmokeCheckError("GraphQL invalid login leaked INTERNAL_ERROR.")
    print(f"[smoke] PASS graphql-invalid-login status={result.status} code={code}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run REST + GraphQL HTTP smoke checks."
    )
    parser.add_argument(
        "--base-url", required=True, help="Base URL, e.g. https://api.auraxis.com.br"
    )
    parser.add_argument(
        "--env-name", default="unknown", help="Environment label for logs"
    )
    parser.add_argument(
        "--timeout", type=int, default=15, help="HTTP timeout in seconds"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[smoke] env={args.env_name} base_url={args.base_url}")
    _check_health(args.base_url, args.timeout)
    _check_graphql_empty_query(args.base_url, args.timeout)
    _check_rest_invalid_login(args.base_url, args.timeout)
    _check_graphql_invalid_login(args.base_url, args.timeout)
    print("[smoke] PASS all checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeCheckError as exc:
        print(f"[smoke] FAIL {exc}", file=sys.stderr)
        raise SystemExit(2)
