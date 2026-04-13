#!/usr/bin/env python3
# ruff: noqa: E501, C901
"""POSTMAN-02 — Generate a Postman Collection v2.1 from openapi.json.

Reads the committed ``openapi.json`` (produced by ``flask openapi-export``)
and outputs a deterministic Postman collection at
``api-tests/postman/auraxis.postman_collection.json``.

Tag → folder mapping, auth headers, suite-profile skip logic, and basic
status-code assertions are applied automatically.  The enrichment config
in ``ENRICHMENT`` lets us attach custom pre-request / test scripts and
example bodies for specific operations.

Usage:
    python3 scripts/openapi_to_postman.py
    # or via npm:
    npm run postman:build
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "openapi.json"
COLLECTION_PATH = ROOT / "api-tests" / "postman" / "auraxis.postman_collection.json"

# ---------------------------------------------------------------------------
# Tag → numbered folder mapping (matches existing README structure)
# ---------------------------------------------------------------------------
TAG_FOLDER_MAP: dict[str, str] = {
    "Health": "00 - Health",
    "Observability": "00 - Health",
    "Autenticação": "01 - Auth",
    "Usuário": "02 - User",
    "Transações": "03 - Transactions",
    "Dashboard": "03 - Transactions",
    "Orçamentos": "04 - Budgets",
    "Metas": "05 - Goals",
    "Wallet": "06 - Wallet",
    "Simulações": "07 - Simulations",
    "Entitlements": "08 - Entitlements",
}
DEFAULT_FOLDER = "99 - Other"

# Per-operation folder override — takes precedence over tag and path-prefix mapping.
# Use this to relocate specific operations (e.g. logout to the end of the run).
OPERATION_FOLDER_OVERRIDE: dict[str, str] = {
    "POST /auth/logout": "99 - Cleanup",
}

# Path-prefix fallback for untagged endpoints
PATH_FOLDER_FALLBACK: dict[str, str] = {
    "/goals": "05 - Goals",
    "/simulations": "07 - Simulations",
    "/budgets": "04 - Budgets",
    "/transactions": "03 - Transactions",
    "/wallet": "06 - Wallet",
    "/auth": "01 - Auth",
    "/user": "02 - User",
}

# Explicit operation ordering within folders.
# Operations listed here are placed first (in given order);
# remaining operations sort alphabetically after them.
OPERATION_ORDER: dict[str, list[str]] = {
    "01 - Auth": [
        "POST /auth/register",
        "POST /auth/login",
        "POST /auth/refresh",
        "GET /user/me",
    ],
    "03 - Transactions": [
        "POST /transactions",
        "GET /transactions",
        "GET /transactions/summary",
        "GET /dashboard/overview",
    ],
    "05 - Goals": [
        "POST /goals",
        "GET /goals",
    ],
    "06 - Wallet": [
        "POST /wallet",
        "GET /wallet",
        "GET /wallet/valuation",
    ],
    "04 - Budgets": [
        "POST /budgets",
        "GET /budgets",
    ],
}

# Folder ordering for deterministic output
FOLDER_ORDER = [
    "00 - Health",
    "01 - Auth",
    "02 - User",
    "03 - Transactions",
    "04 - Budgets",
    "05 - Goals",
    "06 - Wallet",
    "07 - Simulations",
    "08 - Entitlements",
    "99 - Cleanup",
    "99 - Other",
]

# ---------------------------------------------------------------------------
# Public / no-auth endpoints (by path prefix)
# ---------------------------------------------------------------------------
PUBLIC_PATHS = {
    "/healthz",
    "/readiness",
    "/ops/metrics",
    "/ops/observability",
    "/auth/login",
    "/auth/register",
    "/auth/password/forgot",
    "/auth/password/reset",
    "/auth/email/confirm",
    "/auth/email/resend",
    "/simulations/installment-vs-cash/calculate",
}

# ---------------------------------------------------------------------------
# Suite profile lists — which requests belong to smoke / privileged
# ---------------------------------------------------------------------------
SMOKE_OPERATIONS: set[str] = {
    "GET /healthz",
    "POST /auth/register",
    "POST /auth/login",
    "GET /user/me",
    "GET /user/bootstrap",
    "POST /transactions",
    "GET /transactions",
    "GET /transactions/summary",
    "GET /dashboard/overview",
    "POST /goals",
    "GET /goals",
    "POST /goals/simulate",
    "POST /wallet",
    "GET /wallet",
    "GET /wallet/valuation",
    "POST /simulations/installment-vs-cash/calculate",
    "GET /entitlements",
    "GET /budgets",
    "POST /budgets",
}

PRIVILEGED_OPERATIONS: set[str] = {
    "POST /entitlements/admin",
    "DELETE /entitlements/admin/{entitlement_id}",
}

# ---------------------------------------------------------------------------
# Enrichment config — custom bodies, pre-request, test scripts per operation
# ---------------------------------------------------------------------------
ENRICHMENT: dict[str, dict[str, Any]] = {
    "POST /auth/register": {
        "body_override": json.dumps(
            {
                "name": "{{runName}}",
                "email": "{{runEmail}}",
                "password": "{{testPassword}}",
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Register returns 201', function () {",
            "  pm.response.to.have.status(201);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.user) {",
            "  pm.collectionVariables.set('userId', json.data.user.id);",
            "}",
        ],
    },
    "POST /auth/login": {
        "body_override": json.dumps(
            {
                "email": "{{runEmail}}",
                "password": "{{testPassword}}",
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Login returns 200', function () {",
            "  pm.response.to.have.status(200);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.token) {",
            "  pm.collectionVariables.set('authToken', json.data.token);",
            "}",
            "if (json.data && json.data.refresh_token) {",
            "  pm.collectionVariables.set('refreshToken', json.data.refresh_token);",
            "}",
        ],
    },
    "POST /auth/refresh": {
        "body_override": json.dumps(
            {"refresh_token": "{{refreshToken}}"},
            indent=2,
        ),
        "test_lines": [
            "pm.test('Refresh returns 200', function () {",
            "  pm.response.to.have.status(200);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.token) {",
            "  pm.collectionVariables.set('authToken', json.data.token);",
            "}",
        ],
    },
    "POST /transactions": {
        "body_override": json.dumps(
            {
                "description": "Postman test txn {{runSeed}}",
                "value": 42.50,
                "type": "expense",
                "due_date": "{{runTomorrow}}",
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Create transaction returns 201', function () {",
            "  pm.response.to.have.status(201);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.id) {",
            "  pm.collectionVariables.set('transactionId', json.data.id);",
            "}",
        ],
    },
    "POST /goals": {
        "body_override": json.dumps(
            {
                "name": "Goal {{runSeed}}",
                "target_amount": 10000,
                "target_date": "{{runIn365Days}}",
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Create goal returns 201', function () {",
            "  pm.response.to.have.status(201);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.id) {",
            "  pm.collectionVariables.set('goalId', json.data.id);",
            "}",
        ],
    },
    "POST /wallet": {
        "body_override": json.dumps(
            {
                "name": "Test Asset {{runSeed}}",
                "ticker": "PETR4",
                "quantity": 10,
                "register_date": "{{runToday}}",
                "should_be_on_wallet": True,
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Create wallet entry returns 201', function () {",
            "  pm.response.to.have.status(201);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.id) {",
            "  pm.collectionVariables.set('investmentId', json.data.id);",
            "}",
        ],
    },
    "POST /budgets": {
        "body_override": json.dumps(
            {
                "name": "Budget {{runSeed}}",
                "amount": 500.00,
                "month": "{{runMonthRef}}",
            },
            indent=2,
        ),
        "test_lines": [
            "pm.test('Create budget returns 201', function () {",
            "  pm.response.to.have.status(201);",
            "});",
            "var json = pm.response.json();",
            "if (json.data && json.data.id) {",
            "  pm.collectionVariables.set('budgetId', json.data.id);",
            "}",
        ],
    },
    "POST /simulations/installment-vs-cash/calculate": {
        "body_override": json.dumps(
            {
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
            indent=2,
        ),
    },
}

# ---------------------------------------------------------------------------
# Helper: Postman request/item builders
# ---------------------------------------------------------------------------


def _js(lines: list[str]) -> dict[str, Any]:
    return {"exec": lines, "type": "text/javascript"}


def _resolve_ref(spec: dict[str, Any], ref: str) -> dict[str, Any]:
    """Resolve a $ref pointer like '#/components/schemas/Foo'."""
    parts = ref.lstrip("#/").split("/")
    node: Any = spec
    for part in parts:
        node = node.get(part, {})
    return node if isinstance(node, dict) else {}


def _example_from_schema(
    spec: dict[str, Any], schema: dict[str, Any], depth: int = 0
) -> Any:
    """Generate a sample value from an OpenAPI schema (best-effort)."""
    if depth > 4:
        return {}
    if "$ref" in schema:
        schema = _resolve_ref(spec, schema["$ref"])
    if "example" in schema:
        return schema["example"]
    schema_type = schema.get("type", "object")
    if schema_type == "object":
        props = schema.get("properties", {})
        return {k: _example_from_schema(spec, v, depth + 1) for k, v in props.items()}
    if schema_type == "array":
        items = schema.get("items", {})
        return [_example_from_schema(spec, items, depth + 1)]
    if schema_type == "string":
        fmt = schema.get("format", "")
        if fmt == "date":
            return "2026-01-01"
        if fmt == "date-time":
            return "2026-01-01T00:00:00Z"
        if fmt == "email":
            return "user@example.com"
        if fmt == "uuid":
            return "00000000-0000-4000-8000-000000000001"
        return schema.get("enum", ["string"])[0] if "enum" in schema else "string"
    if schema_type == "integer":
        return 1
    if schema_type == "number":
        return 1.0
    if schema_type == "boolean":
        return True
    return None


def _extract_body(spec: dict[str, Any], operation: dict[str, Any]) -> str | None:
    """Extract a JSON body example from requestBody or body parameter."""
    # OpenAPI 3.x requestBody
    rb = operation.get("requestBody", {})
    content = rb.get("content", {}).get("application/json", {})
    if "example" in content:
        return json.dumps(content["example"], indent=2, ensure_ascii=False)
    if "schema" in content:
        sample = _example_from_schema(spec, content["schema"])
        if sample:
            return json.dumps(sample, indent=2, ensure_ascii=False)
    # Swagger 2.x body parameter
    for param in operation.get("parameters", []):
        if param.get("in") == "body" and "schema" in param:
            sample = _example_from_schema(spec, param["schema"])
            if sample:
                return json.dumps(sample, indent=2, ensure_ascii=False)
    return None


def _postman_url(path: str) -> dict[str, Any]:
    """Build a Postman URL object from an OpenAPI path."""
    # Replace {param} with :param for Postman path variables
    postman_path = re.sub(r"\{(\w+)\}", r":\1", path)
    segments = [s for s in postman_path.split("/") if s]
    return {
        "raw": "{{baseUrl}}" + postman_path,
        "host": ["{{baseUrl}}"],
        "path": segments,
    }


def _postman_path_variables(path: str) -> list[dict[str, str]]:
    """Extract path variable placeholders."""
    variables = []
    for match in re.finditer(r"\{(\w+)\}", path):
        name = match.group(1)
        # Map to collection variables where possible
        var_map = {
            "transaction_id": "{{transactionId}}",
            "goal_id": "{{goalId}}",
            "investment_id": "{{investmentId}}",
            "operation_id": "{{operationId}}",
            "simulation_id": "{{simulationId}}",
            "budget_id": "{{budgetId}}",
            "entitlement_id": "{{entitlementId}}",
        }
        variables.append({"key": name, "value": var_map.get(name, f"<{name}>")})
    return variables


def _default_test_lines(method: str, path: str, operation: dict[str, Any]) -> list[str]:
    """Generate basic status code assertion."""
    responses = operation.get("responses", {})
    expected_codes = sorted(responses.keys())
    # Pick the success code
    success = "200"
    for code in expected_codes:
        if code.startswith("2"):
            success = code
            break
    summary = operation.get("summary", f"{method.upper()} {path}")
    safe_summary = summary.replace("'", "\\'")
    return [
        f"pm.test('{safe_summary} — status {success}', function () {{",
        f"  pm.response.to.have.status({success});",
        "});",
    ]


def _request_name(method: str, path: str, operation: dict[str, Any]) -> str:
    """Human-readable request name."""
    summary = operation.get("summary", "")
    if summary:
        return f"{method.upper()} — {summary}"
    # Fallback: method + path
    return f"{method.upper()} {path}"


# ---------------------------------------------------------------------------
# Suite profile pre-request (collection-level)
# ---------------------------------------------------------------------------


def _build_smoke_list(items: list[dict[str, Any]]) -> list[str]:
    """Collect request names that belong to the smoke profile."""
    names = []
    for folder in items:
        for item in folder.get("item", []):
            if item.get("_smoke"):
                names.append(item["name"])
    return names


def _build_privileged_list(items: list[dict[str, Any]]) -> list[str]:
    """Collect request names that belong to the privileged profile."""
    names = []
    for folder in items:
        for item in folder.get("item", []):
            if item.get("_privileged"):
                names.append(item["name"])
    return names


def _suite_profile_prerequest(
    smoke_names: list[str], privileged_names: list[str]
) -> list[str]:
    smoke_json = json.dumps(smoke_names, ensure_ascii=True)
    privileged_json = json.dumps(privileged_names, ensure_ascii=True)
    return [
        f"var smokeRequests = {smoke_json};",
        f"var privilegedOnlyRequests = {privileged_json};",
        "var activeProfile = String(pm.environment.get('suiteProfile') || pm.collectionVariables.get('suiteProfile') || 'full').toLowerCase();",
        "if (!['smoke', 'full', 'privileged'].includes(activeProfile)) {",
        "  throw new Error('Unsupported suiteProfile: ' + activeProfile + '. Use smoke, full or privileged.');",
        "}",
        "pm.collectionVariables.set('suiteProfile', activeProfile);",
        "if (activeProfile === 'smoke' && !smokeRequests.includes(pm.info.requestName)) {",
        "  pm.execution.skipRequest();",
        "}",
        "if (activeProfile === 'full' && privilegedOnlyRequests.includes(pm.info.requestName)) {",
        "  pm.execution.skipRequest();",
        "}",
    ]


def _bootstrap_prerequest() -> list[str]:
    return [
        "// Bootstrap once — keep seed/email stable across the entire run",
        "if (!pm.collectionVariables.get('runSeed')) {",
        "  var now = new Date();",
        "  var seed = String(now.getTime());",
        "  function isoDate(offsetDays) {",
        "    var d = new Date(now);",
        "    d.setUTCDate(d.getUTCDate() + offsetDays);",
        "    return d.toISOString().slice(0, 10);",
        "  }",
        "  function isoMonth(offsetMonths) {",
        "    var d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offsetMonths, 1));",
        "    return d.toISOString().slice(0, 7);",
        "  }",
        "  pm.collectionVariables.set('runSeed', seed);",
        "  pm.collectionVariables.set('runEmail', 'auraxis+' + seed + '@example.com');",
        "  pm.collectionVariables.set('runName', 'auraxis_' + seed);",
        "  pm.collectionVariables.set('runToday', isoDate(0));",
        "  pm.collectionVariables.set('runYesterday', isoDate(-1));",
        "  pm.collectionVariables.set('runTomorrow', isoDate(1));",
        "  pm.collectionVariables.set('runIn30Days', isoDate(30));",
        "  pm.collectionVariables.set('runIn45Days', isoDate(45));",
        "  pm.collectionVariables.set('runIn60Days', isoDate(60));",
        "  pm.collectionVariables.set('runIn180Days', isoDate(180));",
        "  pm.collectionVariables.set('runIn365Days', isoDate(365));",
        "  pm.collectionVariables.set('runMonthRef', isoMonth(0));",
        "}",
    ]


# ---------------------------------------------------------------------------
# Main builder
# ---------------------------------------------------------------------------


def build_collection(spec: dict[str, Any]) -> dict[str, Any]:
    """Convert an OpenAPI spec dict to a Postman Collection v2.1 dict."""
    folders: dict[str, list[dict[str, Any]]] = {}

    for path, methods in sorted(spec.get("paths", {}).items()):
        for method in sorted(methods.keys()):
            if method == "options":
                continue  # skip CORS preflight
            operation = methods[method]
            if not isinstance(operation, dict):
                continue

            op_key = f"{method.upper()} {path}"

            # Per-operation override takes highest priority
            folder_name = OPERATION_FOLDER_OVERRIDE.get(op_key, "")
            if not folder_name:
                tags = operation.get("tags", [])
                tag = tags[0] if tags else "Untagged"
                folder_name = TAG_FOLDER_MAP.get(tag, "")
                if not folder_name or tag == "Untagged":
                    # Fallback: match path prefix
                    for prefix, fname in PATH_FOLDER_FALLBACK.items():
                        if path.startswith(prefix):
                            folder_name = fname
                            break
                    else:
                        folder_name = DEFAULT_FOLDER

            # --- Headers ---
            headers: list[dict[str, str]] = [
                {"key": "X-API-Contract", "value": "v2"},
            ]
            needs_auth = path not in PUBLIC_PATHS
            if needs_auth:
                headers.append(
                    {"key": "Authorization", "value": "Bearer {{authToken}}"}
                )

            # --- Body ---
            enrichment = ENRICHMENT.get(op_key, {})
            body_str = enrichment.get("body_override") or _extract_body(spec, operation)
            if body_str:
                headers.insert(0, {"key": "Content-Type", "value": "application/json"})

            # --- Request object ---
            request: dict[str, Any] = {
                "method": method.upper(),
                "header": headers,
                "url": _postman_url(path),
            }
            path_vars = _postman_path_variables(path)
            if path_vars:
                request["url"]["variable"] = path_vars
            if body_str:
                request["body"] = {"mode": "raw", "raw": body_str}

            # --- Events ---
            events: list[dict[str, Any]] = []
            test_lines = enrichment.get("test_lines") or _default_test_lines(
                method, path, operation
            )
            events.append({"listen": "test", "script": _js(test_lines)})

            prerequest_lines = enrichment.get("prerequest_lines")
            if prerequest_lines:
                events.append({"listen": "prerequest", "script": _js(prerequest_lines)})

            # --- Item ---
            name = _request_name(method, path, operation)
            item: dict[str, Any] = {
                "name": name,
                "request": request,
                "event": events,
            }

            # Internal markers (stripped before output)
            item["_op_key"] = op_key
            if op_key in SMOKE_OPERATIONS:
                item["_smoke"] = True
            if op_key in PRIVILEGED_OPERATIONS:
                item["_privileged"] = True

            folders.setdefault(folder_name, []).append(item)

    # --- Sort items within each folder using OPERATION_ORDER ---
    for folder_name, folder_items in folders.items():
        priority = OPERATION_ORDER.get(folder_name, [])
        priority_index = {op_key: i for i, op_key in enumerate(priority)}

        def _sort_key(
            item: dict[str, Any],
            _pi: dict[str, int] = priority_index,
            _plen: int = len(priority),
        ) -> tuple[int, str]:
            op_key = item.get("_op_key", "")
            if op_key in _pi:
                return (_pi[op_key], op_key)
            return (_plen, item.get("name", ""))

        folder_items.sort(key=_sort_key)

    # --- Assemble folder items in order ---
    ordered_items: list[dict[str, Any]] = []
    for folder_name in FOLDER_ORDER:
        if folder_name in folders:
            ordered_items.append({"name": folder_name, "item": folders[folder_name]})
    # Any remaining folders not in FOLDER_ORDER
    for folder_name in sorted(folders.keys()):
        if folder_name not in {f["name"] for f in ordered_items}:
            ordered_items.append({"name": folder_name, "item": folders[folder_name]})

    # --- Build profile lists ---
    smoke_names = _build_smoke_list(ordered_items)
    privileged_names = _build_privileged_list(ordered_items)

    # --- Strip internal markers ---
    for folder in ordered_items:
        for item in folder.get("item", []):
            item.pop("_smoke", None)
            item.pop("_privileged", None)
            item.pop("_op_key", None)

    # --- Collection-level events ---
    collection_events = [
        {
            "listen": "prerequest",
            "script": _js(
                _bootstrap_prerequest()
                + [""]
                + _suite_profile_prerequest(smoke_names, privileged_names)
            ),
        },
    ]

    # --- Collection variables ---
    collection_variables = [
        {"key": "baseUrl", "value": "http://localhost:5000"},
        {"key": "testPassword", "value": "Test@123456"},
        {"key": "suiteProfile", "value": "full"},
        {"key": "authToken", "value": ""},
        {"key": "refreshToken", "value": ""},
        {"key": "userId", "value": ""},
        {"key": "transactionId", "value": ""},
        {"key": "goalId", "value": ""},
        {"key": "investmentId", "value": ""},
        {"key": "operationId", "value": ""},
        {"key": "simulationId", "value": ""},
        {"key": "budgetId", "value": ""},
        {"key": "entitlementId", "value": ""},
        {"key": "runSeed", "value": ""},
        {"key": "runEmail", "value": ""},
        {"key": "runName", "value": ""},
        {"key": "runToday", "value": ""},
        {"key": "runYesterday", "value": ""},
        {"key": "runTomorrow", "value": ""},
        {"key": "runIn30Days", "value": ""},
        {"key": "runIn45Days", "value": ""},
        {"key": "runIn60Days", "value": ""},
        {"key": "runIn180Days", "value": ""},
        {"key": "runIn365Days", "value": ""},
        {"key": "runMonthRef", "value": ""},
    ]

    return {
        "info": {
            "name": "Auraxis API",
            "description": f"Auto-generated from openapi.json ({len(spec.get('paths', {}))} paths). Do not edit manually — regenerate with: npm run postman:build",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
        },
        "item": ordered_items,
        "event": collection_events,
        "variable": collection_variables,
    }


def main() -> None:
    if not OPENAPI_PATH.exists():
        raise SystemExit(
            f"ERROR: {OPENAPI_PATH} not found. Run: flask openapi-export --output openapi.json"
        )

    spec = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    collection = build_collection(spec)

    COLLECTION_PATH.parent.mkdir(parents=True, exist_ok=True)
    COLLECTION_PATH.write_text(
        json.dumps(collection, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    total_requests = sum(len(folder.get("item", [])) for folder in collection["item"])
    print(
        f"Postman collection written to {COLLECTION_PATH.relative_to(ROOT)} "
        f"({total_requests} requests in {len(collection['item'])} folders)"
    )


if __name__ == "__main__":
    main()
