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
from typing import cast

JSONScalar = str | int | float | bool | None
JSONValue = JSONScalar | list["JSONValue"] | dict[str, "JSONValue"]


@dataclass(frozen=True)
class HttpResult:
    status: int
    body_text: str
    body_json: JSONValue | None


class SmokeCheckError(RuntimeError):
    """Raised when a smoke check cannot pass safely."""


class _MethodPreservingNoRedirect(urllib.request.HTTPRedirectHandler):
    """Disable urllib auto-redirect to preserve method/body on manual follow."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: object,
        code: int,
        msg: str,
        headers: object,
        newurl: str,
    ) -> None:
        return None


def _try_parse_json(body_text: str) -> JSONValue | None:
    if not body_text.strip():
        return None
    try:
        return cast(JSONValue, json.loads(body_text))
    except json.JSONDecodeError:
        return None


def _result_from_status(status: int, body_text: str) -> HttpResult:
    return HttpResult(
        status=status, body_text=body_text, body_json=_try_parse_json(body_text)
    )


def _safe_http_error_body(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace")
    except OSError:
        return ""


def _request_json(
    *,
    method: str,
    url: str,
    payload: dict[str, JSONValue] | None = None,
    timeout: int = 15,
    headers: dict[str, str] | None = None,
) -> HttpResult:
    opener = urllib.request.build_opener(_MethodPreservingNoRedirect())
    request_headers = {"Accept": "application/json"}
    if headers:
        request_headers.update(headers)

    redirect_statuses = {301, 302, 303, 307, 308}
    current_url = url

    for _ in range(5):
        data: bytes | None = None
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            url=current_url,
            data=data,
            headers=request_headers,
            method=method,
        )

        try:
            with opener.open(request, timeout=timeout) as response:
                body_text = response.read().decode("utf-8", errors="replace")
                return _result_from_status(response.status, body_text)
        except urllib.error.HTTPError as exc:
            body_text = _safe_http_error_body(exc)
            status = int(exc.code)
            if status in redirect_statuses:
                location = exc.headers.get("Location")
                if not location:
                    return _result_from_status(status, body_text)
                current_url = urllib.parse.urljoin(current_url, location)
                continue
            return _result_from_status(status, body_text)
        except urllib.error.URLError as exc:
            raise SmokeCheckError(
                f"Network error for {method} {current_url}: {exc}"
            ) from exc

    raise SmokeCheckError(f"Too many redirects for {method} {url}.")


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


def _check_cors_preflight(base_url: str, timeout: int, origin: str) -> None:
    """Send an OPTIONS preflight to /auth/login and verify the CORS response headers."""
    url = _build_url(base_url, "/auth/login")
    result = _request_json(
        method="OPTIONS",
        url=url,
        timeout=timeout,
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
        },
    )
    actual = result.body_text  # not used for header checks, but kept for context
    _ = actual  # suppress unused-variable warning
    # urllib does not expose response headers from HTTPError bodies easily,
    # so we need to perform the OPTIONS request using a lower-level approach.
    # Re-issue the request and capture the real response headers.
    import http.client
    import urllib.parse as _urlparse

    parsed = _urlparse.urlparse(url)
    host = parsed.netloc
    path = parsed.path or "/"
    use_https = parsed.scheme == "https"

    conn: http.client.HTTPConnection
    if use_https:
        import ssl

        ctx = ssl.create_default_context()
        conn = http.client.HTTPSConnection(host, timeout=timeout, context=ctx)
    else:
        conn = http.client.HTTPConnection(host, timeout=timeout)

    try:
        conn.request(
            "OPTIONS",
            path,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
            },
        )
        response = conn.getresponse()
        allow_origin = response.getheader("Access-Control-Allow-Origin")
    finally:
        conn.close()

    if not allow_origin:
        raise SmokeCheckError(
            f"CORS preflight for origin={origin!r}: "
            "Access-Control-Allow-Origin header is missing."
        )
    if allow_origin != origin:
        raise SmokeCheckError(
            f"CORS preflight for origin={origin!r}: "
            f"Access-Control-Allow-Origin={allow_origin!r} (expected {origin!r})."
        )
    print(f"[smoke] PASS cors-preflight origin={origin}")


def _check_graphql_invalid_login(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/graphql")
    mutation = (
        "mutation Login($email: String!, $password: String!) { "
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


def _check_installment_vs_cash_rest_calculate(base_url: str, timeout: int) -> None:
    url = _build_url(base_url, "/simulations/installment-vs-cash/calculate")
    result = _request_json(
        method="POST",
        url=url,
        payload={
            "cash_price": "900.00",
            "installment_count": 3,
            "installment_total": "990.00",
            "first_payment_delay_days": 30,
            "opportunity_rate_type": "manual",
            "opportunity_rate_annual": "12.00",
            "inflation_rate_annual": "4.50",
            "fees_enabled": False,
            "fees_upfront": "0.00",
        },
        timeout=timeout,
        headers={"X-API-Contract": "v2"},
    )
    if result.status != 200:
        raise SmokeCheckError(
            "REST installment-vs-cash calculate expected HTTP 200, "
            f"got {result.status}."
        )
    if not isinstance(result.body_json, dict):
        raise SmokeCheckError(
            "REST installment-vs-cash calculate expected JSON object body."
        )
    data = result.body_json.get("data")
    if not isinstance(data, dict):
        raise SmokeCheckError(
            "REST installment-vs-cash calculate expected wrapped data payload."
        )
    if data.get("tool_id") != "installment_vs_cash":
        raise SmokeCheckError(
            "REST installment-vs-cash calculate returned unexpected tool_id."
        )
    print(f"[smoke] PASS rest-installment-vs-cash-calculate status={result.status}")


def _check_installment_vs_cash_graphql_calculate(
    base_url: str,
    timeout: int,
) -> None:
    url = _build_url(base_url, "/graphql")
    query = """
    query InstallmentVsCashCalculate {
      installmentVsCashCalculate(
        cashPrice: "900.00"
        installmentCount: 3
        installmentTotal: "990.00"
        firstPaymentDelayDays: 30
        opportunityRateType: "manual"
        opportunityRateAnnual: "12.00"
        inflationRateAnnual: "4.50"
        feesEnabled: false
        feesUpfront: "0.00"
      ) {
        toolId
        result {
          recommendedOption
        }
      }
    }
    """
    result = _request_json(
        method="POST",
        url=url,
        payload={"query": query},
        timeout=timeout,
    )
    if result.status != 200:
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate expected HTTP 200, "
            f"got {result.status}."
        )
    if not isinstance(result.body_json, dict):
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate expected JSON object body."
        )
    if result.body_json.get("errors"):
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate returned execution errors."
        )
    data = result.body_json.get("data")
    if not isinstance(data, dict):
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate expected data payload."
        )
    calculation = data.get("installmentVsCashCalculate")
    if not isinstance(calculation, dict):
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate expected result object."
        )
    if calculation.get("toolId") != "installment_vs_cash":
        raise SmokeCheckError(
            "GraphQL installment-vs-cash calculate returned unexpected toolId."
        )
    print(f"[smoke] PASS graphql-installment-vs-cash-calculate status={result.status}")


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
    parser.add_argument(
        "--cors-origin",
        default="https://app.auraxis.com.br",
        help=(
            "Origin to use for the CORS preflight check "
            "(default: https://app.auraxis.com.br)"
        ),
    )
    parser.add_argument(
        "--skip-cors",
        action="store_true",
        default=False,
        help=(
            "Skip the CORS preflight check. Useful for internal health checks "
            "where a browser origin is not expected."
        ),
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print(f"[smoke] env={args.env_name} base_url={args.base_url}")
    _check_health(args.base_url, args.timeout)
    _check_graphql_empty_query(args.base_url, args.timeout)
    _check_rest_invalid_login(args.base_url, args.timeout)
    if not args.skip_cors:
        _check_cors_preflight(args.base_url, args.timeout, args.cors_origin)
    _check_graphql_invalid_login(args.base_url, args.timeout)
    _check_installment_vs_cash_rest_calculate(args.base_url, args.timeout)
    _check_installment_vs_cash_graphql_calculate(args.base_url, args.timeout)
    print("[smoke] PASS all checks")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeCheckError as exc:
        print(f"[smoke] FAIL {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
