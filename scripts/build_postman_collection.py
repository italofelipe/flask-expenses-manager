#!/usr/bin/env python3
# ruff: noqa: E501
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
COLLECTION_PATH = ROOT / "api-tests" / "postman" / "auraxis.postman_collection.json"
SMOKE_REQUESTS = [
    "01 - Healthz",
    "02 - Register user (REST v2)",
    "03 - Login user (REST v2)",
    "04 - Login invalid credentials returns safe error",
    "05 - Me (REST v2)",
    "06 - User bootstrap (REST v2)",
    "01 - Create transaction (REST v2)",
    "04 - List active transactions (REST v2)",
    "05 - Transaction summary by month (REST v2)",
    "06 - Dashboard overview (REST v2)",
    "01 - Create goal (REST v2)",
    "02 - List goals (REST v2)",
    "05 - Goal simulate (REST v2)",
    "01 - Create wallet investment (REST v2)",
    "02 - List wallet investments (REST v2)",
    "10 - Create wallet operation (REST v2)",
    "12 - Wallet operation summary (REST v2)",
    "01 - Installment vs cash calculate (REST public)",
    "02 - Installment vs cash save (REST auth required)",
    "03 - Simulation goal bridge without entitlement returns 403",
    "02 - GraphQL login invalid credentials (safe error)",
    "03 - GraphQL me query (auth required)",
    "04 - GraphQL installment vs cash calculate (public)",
    "01 - List alert preferences (REST v2)",
    "01 - Get my subscription (REST v2)",
    "01 - List entitlements (REST v2)",
    "01 - List shared entries by me (REST v2)",
    "01 - CSV upload preview (REST v2)",
]
PRIVILEGED_ONLY_REQUESTS = [
    "04 - Grant advanced simulations entitlement (optional admin)",
    "05 - Save advanced simulation for success bridges (optional admin)",
    "06 - Simulation goal bridge success (optional admin)",
    "07 - Save fee simulation for planned expense bridge (optional admin)",
    "08 - Simulation planned expense bridge success (optional admin)",
    "09 - Revoke advanced simulations entitlement (optional admin)",
]
PRIVILEGED_PROFILE_REQUESTS = [
    "01 - Healthz",
    "02 - Register user (REST v2)",
    "03 - Login user (REST v2)",
    "05 - Me (REST v2)",
    "06 - User bootstrap (REST v2)",
    "01 - Installment vs cash calculate (REST public)",
    "02 - Installment vs cash save (REST auth required)",
    "03 - Simulation goal bridge without entitlement returns 403",
    *PRIVILEGED_ONLY_REQUESTS,
]


def _js(lines: list[str]) -> dict[str, Any]:
    return {"exec": lines, "type": "text/javascript"}


def _test_event(lines: list[str]) -> dict[str, Any]:
    return {"listen": "test", "script": _js(lines)}


def _prerequest_event(lines: list[str]) -> dict[str, Any]:
    return {"listen": "prerequest", "script": _js(lines)}


def _headers(*items: tuple[str, str]) -> list[dict[str, str]]:
    return [{"key": key, "value": value} for key, value in items]


def _url(raw: str, *, query: list[tuple[str, str]] | None = None) -> dict[str, Any]:
    path = [
        segment
        for segment in raw.split("{{baseUrl}}", 1)[1].split("?")[0].split("/")
        if segment
    ]
    payload: dict[str, Any] = {
        "raw": raw,
        "host": ["{{baseUrl}}"],
        "path": path,
    }
    if query:
        payload["query"] = [{"key": key, "value": value} for key, value in query]
    return payload


def _request(
    *,
    method: str,
    raw_url: str,
    headers: list[dict[str, str]] | None = None,
    body: str | None = None,
    query: list[tuple[str, str]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "method": method,
        "header": headers or [],
        "url": _url(raw_url, query=query),
    }
    if body is not None:
        payload["body"] = {"mode": "raw", "raw": body}
    return payload


def _item(
    name: str,
    request: dict[str, Any],
    *,
    test_lines: list[str] | None = None,
    prerequest_lines: list[str] | None = None,
) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    if prerequest_lines:
        events.append(_prerequest_event(prerequest_lines))
    if test_lines:
        events.append(_test_event(test_lines))
    payload: dict[str, Any] = {"name": name, "request": request}
    if events:
        payload["event"] = events
    return payload


def _folder(name: str, items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"name": name, "item": items}


def _suite_profile_prerequest() -> list[str]:
    smoke_json = json.dumps(SMOKE_REQUESTS, ensure_ascii=True)
    privileged_only_json = json.dumps(PRIVILEGED_ONLY_REQUESTS, ensure_ascii=True)
    privileged_profile_json = json.dumps(
        PRIVILEGED_PROFILE_REQUESTS,
        ensure_ascii=True,
    )
    return [
        f"var smokeRequests = {smoke_json};",
        f"var privilegedOnlyRequests = {privileged_only_json};",
        f"var privilegedProfileRequests = {privileged_profile_json};",
        "var activeProfile = String(pm.environment.get('suiteProfile') || pm.collectionVariables.get('suiteProfile') || 'full').toLowerCase();",
        "if (!['smoke', 'full', 'privileged'].includes(activeProfile)) {",
        "  throw new Error('Unsupported suiteProfile: ' + activeProfile + '. Use smoke, full or privileged.');",
        "}",
        "pm.collectionVariables.set('suiteProfile', activeProfile);",
        "if (activeProfile === 'smoke' && !smokeRequests.includes(pm.info.requestName)) {",
        "  console.log('Skipping request outside smoke profile:', pm.info.requestName);",
        "  pm.execution.skipRequest();",
        "}",
        "if (activeProfile === 'full' && privilegedOnlyRequests.includes(pm.info.requestName)) {",
        "  console.log('Skipping privileged-only request outside privileged profile:', pm.info.requestName);",
        "  pm.execution.skipRequest();",
        "}",
        "if (activeProfile === 'privileged' && !privilegedProfileRequests.includes(pm.info.requestName)) {",
        "  console.log('Skipping request outside privileged profile:', pm.info.requestName);",
        "  pm.execution.skipRequest();",
        "}",
    ]


def _skip_if_privileged_flows_disabled() -> list[str]:
    return [
        "var activeProfile = String(pm.environment.get('suiteProfile') || pm.collectionVariables.get('suiteProfile') || 'full').toLowerCase();",
        "var enabled = String(pm.environment.get('enablePrivilegedFlows') || pm.collectionVariables.get('enablePrivilegedFlows') || 'false').toLowerCase();",
        "var adminToken = pm.environment.get('adminToken') || pm.collectionVariables.get('adminToken') || '';",
        "if (activeProfile !== 'privileged') {",
        "  pm.execution.skipRequest();",
        "}",
        "if (enabled !== 'true' || !adminToken) {",
        "  throw new Error('Privileged profile requires enablePrivilegedFlows=true and adminToken configured.');",
        "}",
    ]


def _bootstrap_prerequest() -> list[str]:
    return [
        "var now = new Date();",
        "var seed = String(now.getTime());",
        "function isoDate(offsetDays) {",
        "  var d = new Date(now);",
        "  d.setUTCDate(d.getUTCDate() + offsetDays);",
        "  return d.toISOString().slice(0, 10);",
        "}",
        "function isoMonth(offsetMonths) {",
        "  var d = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + offsetMonths, 1));",
        "  return d.toISOString().slice(0, 7);",
        "}",
        "pm.collectionVariables.set('runSeed', seed);",
        "pm.collectionVariables.set('runEmail', 'auraxis+' + seed + '@example.com');",
        "pm.collectionVariables.set('runName', 'auraxis_' + seed);",
        "pm.collectionVariables.set('runToday', isoDate(0));",
        "pm.collectionVariables.set('runYesterday', isoDate(-1));",
        "pm.collectionVariables.set('runTomorrow', isoDate(1));",
        "pm.collectionVariables.set('runIn30Days', isoDate(30));",
        "pm.collectionVariables.set('runIn45Days', isoDate(45));",
        "pm.collectionVariables.set('runIn60Days', isoDate(60));",
        "pm.collectionVariables.set('runIn180Days', isoDate(180));",
        "pm.collectionVariables.set('runIn365Days', isoDate(365));",
        "pm.collectionVariables.set('runMonthRef', isoMonth(0));",
        "pm.collectionVariables.set('graphSimulationLabel', 'Notebook ' + seed);",
        "pm.collectionVariables.set('fakeUuid', '00000000-0000-4000-8000-000000000001');",
        "pm.collectionVariables.set('alertCategory', 'system');",
        "pm.collectionVariables.set('nonexistentInvitationToken', 'nonexistent-token-' + seed);",
        "['authToken', 'userId', 'transactionId', 'goalId', 'investmentId', 'operationId', 'simulationId', 'genericSimulationId', 'advancedSimulationId', 'feeSimulationId', 'entitlementId', 'receivableId', 'fiscalDocumentId', 'sharedEntryId', 'invitationId', 'subscriptionId'].forEach(function (key) { pm.collectionVariables.unset(key); });",
    ]


def _json_body(raw: str) -> str:
    return raw.strip() + "\n"


def build_collection() -> dict[str, Any]:
    contract_headers = _headers(
        ("Content-Type", "application/json"), ("X-API-Contract", "v2")
    )
    auth_json_headers = _headers(
        ("Content-Type", "application/json"),
        ("Authorization", "Bearer {{authToken}}"),
        ("X-API-Contract", "v2"),
    )
    auth_contract_headers = _headers(
        ("Authorization", "Bearer {{authToken}}"), ("X-API-Contract", "v2")
    )
    graphql_headers = _headers(("Content-Type", "application/json"))
    graphql_auth_headers = _headers(
        ("Content-Type", "application/json"),
        ("Authorization", "Bearer {{authToken}}"),
    )

    auth_items = [
        _item(
            "01 - Healthz",
            _request(method="GET", raw_url="{{baseUrl}}/healthz"),
            test_lines=[
                "pm.test('healthz status 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "02 - Register user (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/register",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "name": "{{runName}}",
                      "email": "{{runEmail}}",
                      "password": "{{testPassword}}"
                    }
                    """
                ),
            ),
            prerequest_lines=_bootstrap_prerequest(),
            test_lines=[
                "pm.test('register returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.test('register returns canonical success payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.message).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "03 - Login user (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/login",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "email": "{{runEmail}}",
                      "password": "{{testPassword}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('login returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('login returns token and user', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.token).to.be.a('string').and.not.empty;",
                "  pm.expect(body.data.user.id).to.be.a('string').and.not.empty;",
                "});",
                "pm.collectionVariables.set('authToken', body.data.token);",
                "pm.collectionVariables.set('userId', body.data.user.id);",
            ],
        ),
        _item(
            "04 - Login invalid credentials returns safe error",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/login",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "email": "{{runEmail}}",
                      "password": "{{testPasswordWrong}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "var allowed = [401, 429, 503];",
                "pm.test('invalid login returns controlled status', function () { pm.expect(allowed).to.include(pm.response.code); });",
                "var body = pm.response.json();",
                "var code = body && body.error ? body.error.code : null;",
                "pm.test('invalid login never leaks INTERNAL_ERROR', function () { pm.expect(code).to.not.eql('INTERNAL_ERROR'); });",
            ],
        ),
        _item(
            "05 - Me (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/user/me?page=1&limit=10",
                headers=auth_contract_headers,
                query=[("page", "1"), ("limit", "10")],
            ),
            test_lines=[
                "pm.test('me returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('me returns canonical authenticated user data', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.user.email).to.eql(pm.collectionVariables.get('runEmail'));",
                "});",
                "pm.test('me legacy contract emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Contract')).to.eql('v3');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Endpoint')).to.eql('/user/bootstrap');",
                "});",
                "pm.collectionVariables.set('userId', body.data.user.id);",
            ],
        ),
        _item(
            "06 - User bootstrap (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/user/bootstrap?transactions_limit=5",
                headers=auth_contract_headers,
                query=[("transactions_limit", "5")],
            ),
            test_lines=[
                "pm.test('user bootstrap returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('user bootstrap returns explicit aggregate', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.user.identity.email).to.eql(pm.collectionVariables.get('runEmail'));",
                "  pm.expect(body.data.transactions_preview.items).to.be.an('array');",
                "  pm.expect(body.data.wallet.items).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "07 - Profile GET (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/user/profile",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('profile GET returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('profile GET returns user payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.user.email).to.eql(pm.collectionVariables.get('runEmail'));",
                "});",
            ],
        ),
        _item(
            "08 - Profile UPDATE (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/user/profile",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "gender": "outro",
                      "monthly_income": "9000.00",
                      "monthly_expenses": "5000.00",
                      "monthly_investment": "1200.00",
                      "investment_goal_date": "{{runIn365Days}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('profile update returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('profile update persists canonical fields', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.user.gender).to.eql('outro');",
                "});",
            ],
        ),
        _item(
            "09 - Questionnaire GET (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/user/profile/questionnaire",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('questionnaire GET returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('questionnaire exposes five questions', function () {",
                "  pm.expect(body.data.questions).to.be.an('array').with.lengthOf(5);",
                "});",
            ],
        ),
        _item(
            "10 - Questionnaire POST valid answers (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/user/profile/questionnaire",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "answers": [3, 2, 3, 2, 1]
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('questionnaire POST valid returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('questionnaire POST returns suggested profile', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.suggested_profile).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "11 - Questionnaire POST invalid answers (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/user/profile/questionnaire",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "answers": [
                        {"question_id": 1, "score": 3}
                      ]
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('questionnaire invalid payload returns controlled client error', function () {",
                "  pm.expect([400, 422]).to.include(pm.response.code);",
                "});",
            ],
        ),
        _item(
            "12 - Logout (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/logout",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('logout returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('logout returns canonical success payload', function () { pm.expect(body.success).to.eql(true); });",
            ],
        ),
        _item(
            "13 - Login again after logout (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/login",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "email": "{{runEmail}}",
                      "password": "{{testPassword}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('re-login returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('authToken', body.data.token);",
            ],
        ),
        _item(
            "14 - Password forgot unknown email (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/password/forgot",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "email": "unknown-{{runSeed}}@example.com"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('password forgot unknown returns neutral 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('password forgot unknown stays neutral', function () { pm.expect(body.success).to.eql(true); });",
            ],
        ),
        _item(
            "15 - Password forgot known email (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/password/forgot",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "email": "{{runEmail}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('password forgot known returns neutral 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('password forgot known does not expose token', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(JSON.stringify(body)).to.not.include('token');",
                "});",
            ],
        ),
        _item(
            "16 - Password reset invalid token (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/auth/password/reset",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "token": "invalid-token-value-with-sufficient-length-123456",
                      "new_password": "NovaSenha@123"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('password reset invalid token returns 400', function () { pm.response.to.have.status(400); });",
                "var body = pm.response.json();",
                "pm.test('password reset invalid token is a validation error', function () {",
                "  pm.expect(body.success).to.eql(false);",
                "  pm.expect(body.error.code).to.eql('VALIDATION_ERROR');",
                "});",
            ],
        ),
        _item(
            "17 - Salary increase simulation (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/user/simulate-salary-increase",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "base_salary": "5000.00",
                      "base_date": "2024-01-01",
                      "discounts": "500.00",
                      "target_real_increase": "7.50"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('salary increase simulation returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('salary increase simulation returns target payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.recomposition).to.be.a('string').and.not.empty;",
                "  pm.expect(body.data.target).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
    ]

    transaction_items = [
        _item(
            "01 - Create transaction (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/transactions",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "title": "Conta de luz {{runSeed}}",
                      "amount": "150.50",
                      "type": "expense",
                      "status": "pending",
                      "due_date": "{{runToday}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('transaction create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "var transaction = Array.isArray(body.data.transaction) ? body.data.transaction[0] : body.data.transaction;",
                "pm.test('transaction create returns transaction id', function () { pm.expect(transaction.id).to.be.a('string').and.not.empty; });",
                "pm.collectionVariables.set('transactionId', transaction.id);",
            ],
        ),
        _item(
            "02 - Patch transaction by id (REST v2)",
            _request(
                method="PATCH",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "title": "Conta de luz ajustada {{runSeed}}",
                      "amount": "175.90"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('transaction patch returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('transaction patch reflects new title', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.transaction.title).to.include('ajustada');",
                "});",
            ],
        ),
        _item(
            "02b - Put transaction by id compatibility (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "description": "Compat update {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('transaction put compatibility returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('transaction put compatibility emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Method')).to.eql('PATCH');",
                "});",
            ],
        ),
        _item(
            "03 - Create income transaction for reports (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/transactions",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "title": "Freelance {{runSeed}}",
                      "amount": "1200.00",
                      "type": "income",
                      "status": "paid",
                      "due_date": "{{runTomorrow}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('supporting transaction returns 201', function () { pm.response.to.have.status(201); });",
            ],
        ),
        _item(
            "04 - List active transactions (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions?page=1&per_page=20",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "20")],
            ),
            test_lines=[
                "pm.test('transaction list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('transaction list returns pagination', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.meta.pagination.total).to.be.at.least(1);",
                "  pm.expect(body.data.transactions).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "04b - Get transaction by id (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('transaction detail returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('transaction detail returns canonical transaction payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.transaction.id).to.eql(pm.collectionVariables.get('transactionId'));",
                "});",
            ],
        ),
        _item(
            "04c - List active transactions legacy alias (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/list?page=1&per_page=20",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "20")],
            ),
            test_lines=[
                "pm.test('transaction list legacy alias returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('transaction list legacy alias mirrors canonical payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.transactions).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "05 - Transaction summary by month (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/summary?month={{runMonthRef}}",
                headers=auth_contract_headers,
                query=[("month", "{{runMonthRef}}")],
            ),
            test_lines=[
                "pm.test('transaction summary returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('summary includes canonical totals', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data).to.have.property('income_total');",
                "  pm.expect(body.data).to.have.property('expense_total');",
                "});",
            ],
        ),
        _item(
            "06 - Dashboard overview (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/dashboard/overview?month={{runMonthRef}}",
                headers=auth_contract_headers,
                query=[("month", "{{runMonthRef}}")],
            ),
            test_lines=[
                "pm.test('dashboard overview returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('dashboard includes totals and counts', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data).to.have.property('totals');",
                "  pm.expect(body.data).to.have.property('counts');",
                "});",
            ],
        ),
        _item(
            "06b - Transaction dashboard compatibility (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/dashboard?month={{runMonthRef}}",
                headers=auth_contract_headers,
                query=[("month", "{{runMonthRef}}")],
            ),
            test_lines=[
                "pm.test('transaction dashboard compatibility returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('dashboard alias emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Endpoint')).to.eql('/dashboard/overview');",
                "});",
            ],
        ),
        _item(
            "07 - Transaction expenses by period (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/expenses?start_date={{runYesterday}}&end_date={{runTomorrow}}&page=1&per_page=20",
                headers=auth_contract_headers,
                query=[
                    ("start_date", "{{runYesterday}}"),
                    ("end_date", "{{runTomorrow}}"),
                    ("page", "1"),
                    ("per_page", "20"),
                ],
            ),
            test_lines=[
                "pm.test('transaction expenses returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('expenses include data and pagination', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.expenses).to.be.an('array');",
                "  pm.expect(body.meta.pagination).to.be.an('object');",
                "});",
                "pm.test('expenses alias emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Endpoint')).to.eql('/transactions?type=expense');",
                "});",
            ],
        ),
        _item(
            "08 - Transaction due range (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/due-range?start_date={{runYesterday}}&end_date={{runIn30Days}}&page=1&per_page=20",
                headers=auth_contract_headers,
                query=[
                    ("start_date", "{{runYesterday}}"),
                    ("end_date", "{{runIn30Days}}"),
                    ("page", "1"),
                    ("per_page", "20"),
                ],
            ),
            test_lines=[
                "pm.test('transaction due range returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('due range includes canonical items and counts', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.transactions).to.be.an('array');",
                "  pm.expect(body.data.counts).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "09 - Delete transaction by id (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('transaction delete returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('transaction delete returns canonical success', function () { pm.expect(body.success).to.eql(true); });",
            ],
        ),
        _item(
            "10 - List deleted transactions (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/transactions/deleted",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('deleted transactions returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('deleted transactions includes previously deleted item', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.deleted_transactions).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "11 - Bank statement preview (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/bank-statements/preview",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "bank": "nubank",
                      "content": "date,title,amount\\n2026-03-14,Supermercado,-123.45\\n2026-03-15,Salario,5000.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('bank statement preview returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('bank statement preview returns entries', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.entries).to.be.an('array').and.not.empty;",
                "});",
                "pm.collectionVariables.set('bankPreviewEntries', JSON.stringify(body.data.entries));",
            ],
        ),
        _item(
            "12 - Bank statement confirm (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/bank-statements/confirm",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "bank": "nubank",
                      "month": "2026-03",
                      "mode": "selective",
                      "transactions": {{bankPreviewEntries}}
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('bank statement confirm returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.test('bank statement confirm returns imported transactions', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.transactions).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "13 - Restore transaction by id (REST v2)",
            _request(
                method="PATCH",
                raw_url="{{baseUrl}}/transactions/restore/{{transactionId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('transaction restore returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('transaction restore canonical success', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
        _item(
            "14 - Delete transaction again (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('transaction delete again returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "15 - Force delete transaction by id (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/transactions/{{transactionId}}/force",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('transaction force delete returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('transaction force delete canonical success', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
    ]

    goal_items = [
        _item(
            "01 - Create goal (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/goals",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "title": "Reserva de emergencia {{runSeed}}",
                      "description": "Cobrir despesas fixas",
                      "category": "reserva",
                      "target_amount": "15000.00",
                      "current_amount": "2500.00",
                      "priority": 1,
                      "target_date": "{{runIn365Days}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('goal create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('goalId', body.data.goal.id);",
                "pm.test('goal create captures goal id', function () { pm.expect(body.data.goal.id).to.be.a('string').and.not.empty; });",
            ],
        ),
        _item(
            "02 - List goals (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/goals?page=1&per_page=10&status=active",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "10"), ("status", "active")],
            ),
            test_lines=[
                "pm.test('goal list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal list includes pagination', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.meta.pagination.total).to.be.at.least(1);",
                "});",
            ],
        ),
        _item(
            "03 - Get goal by id (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/goals/{{goalId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('goal get returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal get returns requested id', function () { pm.expect(body.data.goal.id).to.eql(pm.collectionVariables.get('goalId')); });",
            ],
        ),
        _item(
            "04 - Goal plan by id (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/goals/{{goalId}}/plan",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('goal plan returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal plan includes recommendation payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.goal_plan.recommendations).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "05 - Goal simulate (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/goals/simulate",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "target_amount": "50000.00",
                      "current_amount": "10000.00",
                      "monthly_income": "12000.00",
                      "monthly_expenses": "7000.00",
                      "monthly_contribution": "2000.00",
                      "target_date": "{{runIn365Days}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('goal simulate returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal simulate returns goal plan payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.goal_plan).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "06 - Goal PATCH by id (REST v2)",
            _request(
                method="PATCH",
                raw_url="{{baseUrl}}/goals/{{goalId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "current_amount": "5000.00",
                      "status": "paused"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('goal patch returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal patch reflects paused status', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.goal.status).to.eql('paused');",
                "});",
            ],
        ),
        _item(
            "07 - Goal PUT by id (REST v2 compat)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/goals/{{goalId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "status": "active",
                      "current_amount": "6500.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('goal put compat returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('goal put compat emits deprecation headers', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Method')).to.eql('PATCH');",
                "});",
            ],
        ),
        _item(
            "08 - Delete goal by id (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/goals/{{goalId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('goal delete returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('goal delete canonical success', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
    ]

    wallet_items = [
        _item(
            "01 - Create wallet investment (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/wallet",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Reserva {{runSeed}}",
                      "value": "1500.00",
                      "quantity": 2,
                      "register_date": "{{runYesterday}}",
                      "should_be_on_wallet": true
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('wallet create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('investmentId', body.data.investment.id);",
                "pm.test('wallet create captures investment id', function () { pm.expect(body.data.investment.id).to.be.a('string').and.not.empty; });",
            ],
        ),
        _item(
            "02 - List wallet investments (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet?page=1&per_page=10",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "10")],
            ),
            test_lines=[
                "pm.test('wallet list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet list includes pagination and items', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.items).to.be.an('array');",
                "  pm.expect(body.meta.pagination).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "03 - Get wallet investment detail (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet detail returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet detail returns investment payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.investment.id).to.eql(pm.collectionVariables.get('investmentId'));",
                "});",
            ],
        ),
        _item(
            "04 - Patch wallet investment (REST v2)",
            _request(
                method="PATCH",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "value": "2000.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('wallet patch returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet patch keeps history', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.investment.history).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "05 - Put wallet investment (compat REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "value": "2000.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('wallet put returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet put emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Method')).to.eql('PATCH');",
                "});",
                "pm.test('wallet put keeps history', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.investment.history).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "06 - Wallet investment history (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/history?page=1&per_page=10",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "10")],
            ),
            test_lines=[
                "pm.test('wallet history returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet history includes pagination', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.items).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "07 - Wallet portfolio valuation (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/valuation",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet valuation returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('wallet valuation returns canonical payload', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
        _item(
            "08 - Wallet portfolio valuation history (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/valuation/history?start_date={{runYesterday}}&end_date={{runToday}}",
                headers=auth_contract_headers,
                query=[
                    ("start_date", "{{runYesterday}}"),
                    ("end_date", "{{runToday}}"),
                ],
            ),
            test_lines=[
                "pm.test('wallet valuation history returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('wallet valuation history returns canonical payload', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
        _item(
            "09 - Wallet investment valuation (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/valuation",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet investment valuation returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet investment valuation returns valuation object', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.valuation).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "10 - Create wallet operation (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "operation_type": "buy",
                      "quantity": "2.5",
                      "unit_price": "35.40",
                      "fees": "1.20",
                      "executed_at": "{{runYesterday}}",
                      "notes": "Compra inicial {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('wallet operation create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('operationId', body.data.operation.id);",
                "pm.test('wallet operation create captures operation id', function () { pm.expect(body.data.operation.id).to.be.a('string').and.not.empty; });",
            ],
        ),
        _item(
            "11 - List wallet operations (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations?page=1&per_page=10",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "10")],
            ),
            test_lines=[
                "pm.test('wallet operation list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet operation list includes items', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.items).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "12 - Wallet operation summary (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations/summary",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet operation summary returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet operation summary returns summary object', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.summary).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "13 - Wallet operation position (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations/position",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet operation position returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet operation position returns position object', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.position).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "14 - Wallet invested amount by date (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations/invested-amount?date={{runToday}}",
                headers=auth_contract_headers,
                query=[("date", "{{runToday}}")],
            ),
            test_lines=[
                "pm.test('wallet invested amount returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet invested amount returns result object', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.result).to.be.an('object');",
                "});",
            ],
        ),
        _item(
            "15 - Update wallet operation (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations/{{operationId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "notes": "Atualizada {{runSeed}}",
                      "fees": "2.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('wallet operation update returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('wallet operation update reflects notes', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.operation.notes).to.include('Atualizada');",
                "});",
            ],
        ),
        _item(
            "16 - Delete wallet operation (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}/operations/{{operationId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet operation delete returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('wallet operation delete canonical success', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
        _item(
            "17 - Delete wallet investment (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/wallet/{{investmentId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('wallet delete returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('wallet delete canonical success', function () { pm.expect(pm.response.json().success).to.eql(true); });",
            ],
        ),
    ]

    simulation_items = [
        _item(
            "01 - Installment vs cash calculate (REST public)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/installment-vs-cash/calculate",
                headers=contract_headers,
                body=_json_body(
                    """
                    {
                      "cash_price": "900.00",
                      "installment_count": 3,
                      "installment_total": "990.00",
                      "first_payment_delay_days": 30,
                      "opportunity_rate_type": "manual",
                      "opportunity_rate_annual": "12.00",
                      "inflation_rate_annual": "4.50",
                      "fees_enabled": false,
                      "fees_upfront": "0.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('simulation calculate returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('simulation calculate returns canonical result', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.tool_id).to.eql('installment_vs_cash');",
                "});",
            ],
        ),
        _item(
            "02 - Installment vs cash save (REST auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/installment-vs-cash",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "cash_price": "900.00",
                      "installment_count": 3,
                      "installment_total": "990.00",
                      "first_payment_delay_days": 30,
                      "opportunity_rate_type": "manual",
                      "opportunity_rate_annual": "12.00",
                      "inflation_rate_annual": "4.50",
                      "fees_enabled": false,
                      "fees_upfront": "0.00",
                      "scenario_label": "{{graphSimulationLabel}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('simulation save returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('simulationId', body.data.simulation.id);",
                "pm.test('simulation save returns persisted simulation id', function () { pm.expect(body.data.simulation.id).to.be.a('string').and.not.empty; });",
            ],
        ),
        _item(
            "03 - Simulation goal bridge without entitlement returns 403",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/{{simulationId}}/goal",
                headers=_headers(
                    ("Content-Type", "application/json"),
                    ("Authorization", "Bearer {{authToken}}"),
                ),
                body=_json_body(
                    """
                    {
                      "title": "Notebook novo {{runSeed}}",
                      "selected_option": "cash"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('simulation goal bridge without entitlement returns 403', function () { pm.response.to.have.status(403); });",
            ],
        ),
        _item(
            "04 - Grant advanced simulations entitlement (optional admin)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/entitlements/admin",
                headers=_headers(
                    ("Content-Type", "application/json"),
                    ("Authorization", "Bearer {{adminToken}}"),
                    ("X-API-Contract", "v2"),
                ),
                body=_json_body(
                    """
                    {
                      "user_id": "{{userId}}",
                      "feature_key": "advanced_simulations",
                      "source": "postman_e2e"
                    }
                    """
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('entitlement grant returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('entitlementId', body.data.entitlement.id);",
            ],
        ),
        _item(
            "05 - Save advanced simulation for success bridges (optional admin)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/installment-vs-cash/save",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "cash_price": "1500.00",
                      "installment_count": 5,
                      "installment_total": "1650.00",
                      "first_payment_delay_days": 30,
                      "opportunity_rate_type": "manual",
                      "opportunity_rate_annual": "12.00",
                      "inflation_rate_annual": "4.50",
                      "fees_enabled": false,
                      "fees_upfront": "0.00",
                      "scenario_label": "Bridge {{runSeed}}"
                    }
                    """
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('advanced simulation save returns 201', function () { pm.response.to.have.status(201); });",
                "pm.collectionVariables.set('advancedSimulationId', pm.response.json().data.simulation.id);",
            ],
        ),
        _item(
            "06 - Simulation goal bridge success (optional admin)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/{{advancedSimulationId}}/goal",
                headers=_headers(
                    ("Content-Type", "application/json"),
                    ("Authorization", "Bearer {{authToken}}"),
                ),
                body=_json_body(
                    """
                    {
                      "title": "Notebook premium {{runSeed}}",
                      "selected_option": "cash"
                    }
                    """
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('simulation goal bridge success returns 201', function () { pm.response.to.have.status(201); });",
            ],
        ),
        _item(
            "07 - Save fee simulation for planned expense bridge (optional admin)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/installment-vs-cash/save",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "cash_price": "900.00",
                      "installment_count": 3,
                      "installment_total": "990.00",
                      "first_payment_delay_days": 30,
                      "opportunity_rate_type": "manual",
                      "opportunity_rate_annual": "12.00",
                      "inflation_rate_annual": "4.50",
                      "fees_enabled": true,
                      "fees_upfront": "60.00",
                      "scenario_label": "Fees {{runSeed}}"
                    }
                    """
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('fee simulation save returns 201', function () { pm.response.to.have.status(201); });",
                "pm.collectionVariables.set('feeSimulationId', pm.response.json().data.simulation.id);",
            ],
        ),
        _item(
            "09 - Installment vs cash save legacy alias (REST v2 compat)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/installment-vs-cash/save",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "cash_price": "1000.00",
                      "installment_count": 4,
                      "installment_total": "1080.00",
                      "first_payment_delay_days": 30,
                      "opportunity_rate_type": "manual",
                      "opportunity_rate_annual": "12.00",
                      "inflation_rate_annual": "4.50",
                      "fees_enabled": false,
                      "fees_upfront": "0.00",
                      "scenario_label": "Compat {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('simulation save compat returns 201', function () { pm.response.to.have.status(201); });",
                "pm.test('simulation save compat emits deprecation headers', function () {",
                "  pm.expect(pm.response.headers.get('Deprecation')).to.eql('true');",
                "  pm.expect(pm.response.headers.get('X-Auraxis-Successor-Endpoint')).to.eql('/simulations/installment-vs-cash');",
                "});",
            ],
        ),
        _item(
            "08 - Simulation planned expense bridge success (optional admin)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations/{{feeSimulationId}}/planned-expense",
                headers=_headers(
                    ("Content-Type", "application/json"),
                    ("Authorization", "Bearer {{authToken}}"),
                ),
                body=_json_body(
                    """
                    {
                      "title": "Notebook novo {{runSeed}}",
                      "selected_option": "installment",
                      "first_due_date": "{{runIn30Days}}"
                    }
                    """
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('simulation planned expense bridge success returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.test('simulation planned expense returns generated transactions', function () {",
                "  pm.expect(body.transactions).to.be.an('array').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "09 - Revoke advanced simulations entitlement (optional admin)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/entitlements/admin/{{entitlementId}}",
                headers=_headers(
                    ("Authorization", "Bearer {{adminToken}}"), ("X-API-Contract", "v2")
                ),
            ),
            prerequest_lines=_skip_if_privileged_flows_disabled(),
            test_lines=[
                "pm.test('entitlement revoke returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "10 - Save generic simulation (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/simulations",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "tool_id": "salary_projection",
                      "rule_version": "v1",
                      "inputs": {
                        "base_salary": "5000.00",
                        "target_raise": "7.50"
                      },
                      "result": {
                        "projected_salary": "5375.00"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('generic simulation create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('genericSimulationId', body.data.simulation.id);",
                "pm.test('generic simulation create captures id', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.simulation.id).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "11 - List saved simulations (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/simulations?page=1&per_page=20",
                headers=auth_contract_headers,
                query=[("page", "1"), ("per_page", "20")],
            ),
            test_lines=[
                "pm.test('simulation list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('simulation list includes pagination and items', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.items).to.be.an('array');",
                "  pm.expect(body.meta.pagination.total).to.be.at.least(1);",
                "});",
            ],
        ),
        _item(
            "12 - Get saved simulation by id (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/simulations/{{genericSimulationId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('simulation get returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('simulation get returns requested id', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.simulation.id).to.eql(pm.collectionVariables.get('genericSimulationId'));",
                "});",
            ],
        ),
        _item(
            "13 - Delete saved simulation by id (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/simulations/{{genericSimulationId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('simulation delete returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('simulation delete canonical success', function () {",
                "  pm.expect(pm.response.json().success).to.eql(true);",
                "});",
            ],
        ),
    ]

    alert_items = [
        _item(
            "01 - List alert preferences (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/alerts/preferences",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('alert preferences returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('alert preferences returns list payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.preferences).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "02 - Update alert preference (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/alerts/preferences/{{alertCategory}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "enabled": true,
                      "channels": ["in_app"],
                      "global_opt_out": false
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('alert preference update returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('alert preference update returns preference payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.preference.category).to.eql(pm.collectionVariables.get('alertCategory'));",
                "});",
            ],
        ),
        _item(
            "03 - List alerts (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/alerts?unread_only=false",
                headers=auth_contract_headers,
                query=[("unread_only", "false")],
            ),
            test_lines=[
                "pm.test('alerts list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('alerts list returns alerts array', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.alerts).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "04 - Mark alert as read for nonexistent id returns 404",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/alerts/{{fakeUuid}}/read",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('alert read missing id returns 404', function () { pm.response.to.have.status(404); });",
            ],
        ),
        _item(
            "05 - Delete alert for nonexistent id returns 404",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/alerts/{{fakeUuid}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('alert delete missing id returns 404', function () { pm.response.to.have.status(404); });",
            ],
        ),
    ]

    auxiliary_items = [
        _item(
            "01 - List tags (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/tags",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('tags list returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "02 - Create tag (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/tags",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Casa {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('tag create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('tagId', body.data.tag.id);",
            ],
        ),
        _item(
            "03 - Update tag (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/tags/{{tagId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Casa ajustada {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('tag update returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "04 - Delete tag (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/tags/{{tagId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('tag delete returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "05 - List accounts (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/accounts",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('accounts list returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "06 - Create account (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/accounts",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Conta principal {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('account create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('accountId', body.data.account.id);",
            ],
        ),
        _item(
            "07 - Update account (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/accounts/{{accountId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Conta ajuste {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('account update returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "08 - Delete account (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/accounts/{{accountId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('account delete returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "09 - List credit cards (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/credit-cards",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('credit cards list returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "10 - Create credit card (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/credit-cards",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Cartao {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('credit card create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.collectionVariables.set('creditCardId', body.data.credit_card.id);",
            ],
        ),
        _item(
            "11 - Update credit card (REST v2)",
            _request(
                method="PUT",
                raw_url="{{baseUrl}}/credit-cards/{{creditCardId}}",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "name": "Cartao ajuste {{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('credit card update returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "12 - Delete credit card (REST v2)",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/credit-cards/{{creditCardId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('credit card delete returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
    ]

    subscription_items = [
        _item(
            "00 - List billing plans (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/subscriptions/plans",
                headers=contract_headers,
            ),
            test_lines=[
                "pm.test('subscription plans returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('subscription plans returns canonical offers', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.plans).to.be.an('array');",
                "  pm.expect(body.data.plans[1].slug).to.eql('premium_monthly');",
                "});",
            ],
        ),
        _item(
            "01 - Get my subscription (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/subscriptions/me",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('subscription me returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('subscription me returns subscription payload', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.subscription.id).to.be.a('string').and.not.empty;",
                "});",
                "pm.collectionVariables.set('subscriptionId', pm.response.json().data.subscription.id);",
            ],
        ),
        _item(
            "02 - Create checkout session (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/subscriptions/checkout",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "plan_slug": "premium_monthly"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('subscription checkout returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "pm.test('subscription checkout returns checkout url', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.plan_slug).to.eql('premium_monthly');",
                "  pm.expect(body.data.checkout_url).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "03 - Cancel subscription (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/subscriptions/cancel",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('subscription cancel returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('subscription cancel returns canceled status', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.subscription.status).to.eql('canceled');",
                "});",
            ],
        ),
        _item(
            "04 - Webhook invalid signature returns 401",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/subscriptions/webhook",
                headers=_headers(
                    ("Content-Type", "application/json"),
                    ("X-Billing-Signature", "invalid-signature"),
                ),
                body=_json_body(
                    """
                    {
                      "event": "subscription.activated",
                      "subscription_id": "sub_fake"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('subscription webhook invalid signature returns 401', function () { pm.response.to.have.status(401); });",
            ],
        ),
    ]

    entitlement_items = [
        _item(
            "01 - List entitlements (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/entitlements",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('entitlements list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('entitlements list returns items array', function () {",
                "  pm.expect(body.success).to.eql(true);",
                "  pm.expect(body.data.items).to.be.an('array');",
                "});",
            ],
        ),
        _item(
            "02 - Check entitlement missing feature key returns 400",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/entitlements/check",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('entitlement check missing feature key returns 400', function () { pm.response.to.have.status(400); });",
            ],
        ),
    ]

    shared_entries_items = [
        _item(
            "01 - List shared entries by me (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/shared-entries/by-me",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared entries by me returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('shared entries by me returns array', function () { pm.expect(pm.response.json().data.shared_entries).to.be.an('array'); });",
            ],
        ),
        _item(
            "02 - List shared entries with me (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/shared-entries/with-me",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared entries with me returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('shared entries with me returns array', function () { pm.expect(pm.response.json().data.shared_entries).to.be.an('array'); });",
            ],
        ),
        _item(
            "03 - Create shared entry missing fields returns 400",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/shared-entries",
                headers=auth_json_headers,
                body=_json_body("{}"),
            ),
            test_lines=[
                "pm.test('shared entry missing fields returns 400', function () { pm.response.to.have.status(400); });",
            ],
        ),
        _item(
            "04 - List invitations (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/shared-entries/invitations",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared invitations list returns 200', function () { pm.response.to.have.status(200); });",
                "pm.test('shared invitations list returns array', function () { pm.expect(pm.response.json().data.invitations).to.be.an('array'); });",
            ],
        ),
        _item(
            "05 - Create invitation missing fields returns 400",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/shared-entries/invitations",
                headers=auth_json_headers,
                body=_json_body("{}"),
            ),
            test_lines=[
                "pm.test('shared invitation missing fields returns 400', function () { pm.response.to.have.status(400); });",
            ],
        ),
        _item(
            "06 - Accept nonexistent invitation returns 404",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/shared-entries/invitations/{{nonexistentInvitationToken}}/accept",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared invitation accept missing token returns 404', function () { pm.response.to.have.status(404); });",
            ],
        ),
        _item(
            "07 - Delete nonexistent shared entry returns 404",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/shared-entries/{{fakeUuid}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared entry delete missing id returns 404', function () { pm.response.to.have.status(404); });",
            ],
        ),
        _item(
            "08 - Delete nonexistent invitation returns 404",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/shared-entries/invitations/{{fakeUuid}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('shared invitation delete missing id returns 404', function () { pm.response.to.have.status(404); });",
            ],
        ),
    ]

    fiscal_items = [
        _item(
            "01 - CSV upload preview (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/fiscal/csv/upload",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "content": "description,amount,date,category,external_id\\nConsultoria,1500.00,2026-03-22,consulting,ext-{{runSeed}}\\nLicenca,900.00,2026-03-23,software,ext2-{{runSeed}}",
                      "column_map": {
                        "description": "description",
                        "amount": "amount",
                        "date": "date",
                        "category": "category",
                        "external_id": "external_id"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('fiscal csv upload returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('fiscal csv upload returns preview rows', function () { pm.expect(body.data.preview || body.preview).to.be.an('array'); });",
            ],
        ),
        _item(
            "02 - CSV confirm import (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/fiscal/csv/confirm",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "content": "description,amount,date,category,external_id\\nConsultoria,1500.00,2026-03-22,consulting,ext-{{runSeed}}\\nLicenca,900.00,2026-03-23,software,ext2-{{runSeed}}",
                      "column_map": {
                        "description": "description",
                        "amount": "amount",
                        "date": "date",
                        "category": "category",
                        "external_id": "external_id"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('fiscal csv confirm returns 201', function () { pm.response.to.have.status(201); });",
            ],
        ),
        _item(
            "03 - List receivables (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/fiscal/receivables",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('fiscal receivables list returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "var items = body.data ? body.data.receivables : body.receivables;",
                "pm.test('fiscal receivables list returns items array', function () { pm.expect(items).to.be.an('array'); });",
                "if (items.length > 0) { pm.collectionVariables.set('receivableId', items[0].id); }",
            ],
        ),
        _item(
            "04 - Create manual receivable (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/fiscal/receivables",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "description": "Servico extra {{runSeed}}",
                      "amount": "2500.00",
                      "expected_date": "{{runTomorrow}}",
                      "category": "consulting"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('fiscal receivable create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "var receivable = body.data ? body.data.receivable : body.receivable;",
                "pm.collectionVariables.set('receivableId', receivable.id);",
                "pm.test('fiscal receivable create returns id', function () { pm.expect(receivable.id).to.be.a('string').and.not.empty; });",
            ],
        ),
        _item(
            "05 - Mark receivable as received (REST v2)",
            _request(
                method="PATCH",
                raw_url="{{baseUrl}}/fiscal/receivables/{{receivableId}}/receive",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "received_date": "{{runToday}}",
                      "received_amount": "2500.00"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('fiscal receivable receive returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "06 - Receivables summary (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/fiscal/receivables/summary",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('fiscal receivables summary returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "07 - Delete settled receivable returns 409",
            _request(
                method="DELETE",
                raw_url="{{baseUrl}}/fiscal/receivables/{{receivableId}}",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('fiscal receivable delete settled returns 409', function () { pm.response.to.have.status(409); });",
            ],
        ),
        _item(
            "08 - List fiscal documents (REST v2)",
            _request(
                method="GET",
                raw_url="{{baseUrl}}/fiscal/fiscal-documents",
                headers=auth_contract_headers,
            ),
            test_lines=[
                "pm.test('fiscal documents list returns 200', function () { pm.response.to.have.status(200); });",
            ],
        ),
        _item(
            "09 - Create fiscal document (REST v2)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/fiscal/fiscal-documents",
                headers=auth_json_headers,
                body=_json_body(
                    """
                    {
                      "type": "service_invoice",
                      "amount": "1999.90",
                      "issued_at": "{{runToday}}",
                      "counterpart_name": "Cliente {{runSeed}}",
                      "external_id": "invoice-{{runSeed}}"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('fiscal document create returns 201', function () { pm.response.to.have.status(201); });",
                "var body = pm.response.json();",
                "var doc = body.data ? body.data.fiscal_document : body.fiscal_document;",
                "pm.collectionVariables.set('fiscalDocumentId', doc.id);",
                "pm.test('fiscal document create returns id', function () { pm.expect(doc.id).to.be.a('string').and.not.empty; });",
            ],
        ),
    ]

    graphql_items = [
        _item(
            "01 - GraphQL empty query (validation error)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_headers,
                body=_json_body(
                    """
                    {
                      "query": "   "
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql empty query returns 400', function () { pm.response.to.have.status(400); });",
                "var body = pm.response.json();",
                "var firstErr = body.errors && body.errors[0] ? body.errors[0] : {};",
                "pm.test('graphql empty query uses VALIDATION_ERROR', function () { pm.expect(firstErr.extensions.code).to.eql('VALIDATION_ERROR'); });",
            ],
        ),
        _item(
            "02 - GraphQL login invalid credentials (safe error)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation Login($email: String!, $password: String!) { login(email: $email, password: $password) { token message } }",
                      "variables": {
                        "email": "{{runEmail}}",
                        "password": "{{testPasswordWrong}}"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql invalid login transport status is 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "var firstErr = body.errors && body.errors[0] ? body.errors[0] : {};",
                "pm.test('graphql invalid login exposes public UNAUTHORIZED code', function () { pm.expect(firstErr.extensions.code).to.eql('UNAUTHORIZED'); });",
            ],
        ),
        _item(
            "03 - GraphQL me query (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "query Me { me { id email name } }"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql me returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql me returns authenticated user', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.me.email).to.eql(pm.collectionVariables.get('runEmail'));",
                "});",
            ],
        ),
        _item(
            "04 - GraphQL forgot password stays neutral",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation ForgotPassword($email: String!) { forgotPassword(email: $email) { message } }",
                      "variables": {
                        "email": "unknown-user@email.com"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql forgot password returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql forgot password stays neutral', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.forgotPassword.message).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "05 - GraphQL reset password invalid token is public validation error",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation ResetPassword($token: String!, $newPassword: String!) { resetPassword(token: $token, newPassword: $newPassword) { message } }",
                      "variables": {
                        "token": "invalid-token-value-with-sufficient-length-123456",
                        "newPassword": "NovaSenha@123"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql reset invalid token returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "var firstErr = body.errors && body.errors[0] ? body.errors[0] : {};",
                "pm.test('graphql reset invalid token returns VALIDATION_ERROR', function () { pm.expect(firstErr.extensions.code).to.eql('VALIDATION_ERROR'); });",
            ],
        ),
        _item(
            "06 - GraphQL installment vs cash calculate (public)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_headers,
                body=_json_body(
                    """
                    {
                      "query": "query InstallmentVsCashCalculate { installmentVsCashCalculate(cashPrice: \\"900.00\\", installmentCount: 3, installmentTotal: \\"990.00\\", firstPaymentDelayDays: 30, opportunityRateType: \\"manual\\", opportunityRateAnnual: \\"12.00\\", inflationRateAnnual: \\"4.50\\", feesEnabled: false, feesUpfront: \\"0.00\\") { toolId result { recommendedOption } } }"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql installment calculate returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql installment calculate returns tool id', function () { pm.expect(body.data.installmentVsCashCalculate.toolId).to.eql('installment_vs_cash'); });",
            ],
        ),
        _item(
            "07 - GraphQL installment vs cash save (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation SaveInstallmentVsCashSimulation { saveInstallmentVsCashSimulation(cashPrice: \\"900.00\\", installmentCount: 3, installmentTotal: \\"990.00\\", firstPaymentDelayDays: 30, opportunityRateType: \\"manual\\", opportunityRateAnnual: \\"12.00\\", inflationRateAnnual: \\"4.50\\", feesEnabled: true, feesUpfront: \\"60.00\\", scenarioLabel: \\"Notebook {{runSeed}}\\") { message simulation { id toolId saved } calculation { toolId } } }"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql installment save returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql installment save persists simulation', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.saveInstallmentVsCashSimulation.simulation.saved).to.eql(true);",
                "});",
            ],
        ),
        _item(
            "08 - GraphQL transaction dashboard seed (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation SeedExpense($title: String!, $amount: String!, $dueDate: String!) { createTransaction(title: $title, amount: $amount, type: \\"expense\\", dueDate: $dueDate) { items { id title } } }",
                      "variables": {
                        "title": "Conta luz {{runSeed}}",
                        "amount": "150.00",
                        "dueDate": "{{runToday}}"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql transaction seed returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql transaction seed creates an item', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.createTransaction.items[0].id).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "09 - GraphQL transaction reads and dashboard (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "query GraphqlDashboard($month: String!, $initialDate: String!, $finalDate: String!) { transactions(page: 1, perPage: 10) { items { id title } pagination { total } } transactionSummary(month: $month, page: 1, pageSize: 10) { month pagination { total } } transactionDashboard(month: $month) { month counts { totalTransactions } } transactionDueRange(initialDate: $initialDate, finalDate: $finalDate, page: 1, perPage: 10, orderBy: \\"overdue_first\\") { counts { totalTransactions } pagination { total } } }",
                      "variables": {
                        "month": "{{runMonthRef}}",
                        "initialDate": "{{runYesterday}}",
                        "finalDate": "{{runToday}}"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql dashboard returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql dashboard aggregates transaction data', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.transactions.items[0].id).to.be.a('string').and.not.empty;",
                "  pm.expect(body.data.transactionSummary.month).to.eql(pm.collectionVariables.get('runMonthRef'));",
                "  pm.expect(body.data.transactionDashboard.month).to.eql(pm.collectionVariables.get('runMonthRef'));",
                "  pm.expect(body.data.transactionDueRange.counts.totalTransactions).to.be.at.least(1);",
                "});",
            ],
        ),
        _item(
            "10 - GraphQL wallet create (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation AddWalletEntry { addWalletEntry(name: \\"Reserva {{runSeed}}\\", value: 1000, registerDate: \\"{{runToday}}\\", shouldBeOnWallet: true) { item { id name assetClass } } }"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql wallet create returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "var item = body.data.addWalletEntry.item;",
                "pm.collectionVariables.set('graphqlWalletId', item.id);",
                "pm.test('graphql wallet create stores investment id', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(item.id).to.be.a('string').and.not.empty;",
                "});",
            ],
        ),
        _item(
            "11 - GraphQL wallet list and valuation (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "query WalletCoverage($investmentId: UUID!) { walletEntries(page: 1, perPage: 10) { pagination { total } items { id name shouldBeOnWallet } } investmentValuation(investmentId: $investmentId) { investmentId assetClass valuationSource } portfolioValuation { summary { totalInvestments } } }",
                      "variables": {
                        "investmentId": "{{graphqlWalletId}}"
                      }
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql wallet coverage returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql wallet coverage returns canonical portfolio payload', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.walletEntries.pagination.total).to.be.at.least(1);",
                "  pm.expect(body.data.investmentValuation.investmentId).to.eql(pm.collectionVariables.get('graphqlWalletId'));",
                "  pm.expect(body.data.portfolioValuation.summary.totalInvestments).to.be.at.least(1);",
                "});",
            ],
        ),
        _item(
            "12 - GraphQL logout mutation (auth required)",
            _request(
                method="POST",
                raw_url="{{baseUrl}}/graphql",
                headers=graphql_auth_headers,
                body=_json_body(
                    """
                    {
                      "query": "mutation Logout { logout { ok message } }"
                    }
                    """
                ),
            ),
            test_lines=[
                "pm.test('graphql logout returns 200', function () { pm.response.to.have.status(200); });",
                "var body = pm.response.json();",
                "pm.test('graphql logout confirms success', function () {",
                "  pm.expect(body.errors).to.eql(undefined);",
                "  pm.expect(body.data.logout.ok).to.eql(true);",
                "});",
            ],
        ),
    ]

    collection = {
        "info": {
            "_postman_id": "3fd49b04-3416-4cf2-9048-b58abf132a20",
            "name": "Auraxis API - Canonical E2E and Smoke",
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
            "description": (
                "Canonical black-box suite for Auraxis API. Organized by domain, "
                "validated by Newman in CI, and designed for direct Postman import. "
                "Privileged flows are optional and gated by adminToken + enablePrivilegedFlows."
                " Use the dedicated privileged profile when executing admin-only coverage."
            ),
        },
        "event": [
            _prerequest_event(_suite_profile_prerequest()),
        ],
        "item": [
            _folder("00 - Auth and User Bootstrap", auth_items),
            _folder("01 - Transactions", transaction_items),
            _folder("02 - Goals", goal_items),
            _folder("03 - Wallet", wallet_items),
            _folder("04 - Simulations", simulation_items),
            _folder("05 - Alerts", alert_items),
            _folder(
                "06 - Subscriptions and Entitlements",
                subscription_items + entitlement_items,
            ),
            _folder("07 - Shared Entries", shared_entries_items),
            _folder("08 - Fiscal", fiscal_items),
            _folder("09 - Tags, Accounts and Credit Cards", auxiliary_items),
            _folder("10 - GraphQL", graphql_items),
        ],
        "variable": [
            {"key": "runSeed", "value": ""},
            {"key": "runEmail", "value": ""},
            {"key": "runName", "value": ""},
            {"key": "authToken", "value": ""},
            {"key": "userId", "value": ""},
            {"key": "transactionId", "value": ""},
            {"key": "goalId", "value": ""},
            {"key": "investmentId", "value": ""},
            {"key": "operationId", "value": ""},
            {"key": "simulationId", "value": ""},
            {"key": "genericSimulationId", "value": ""},
            {"key": "advancedSimulationId", "value": ""},
            {"key": "feeSimulationId", "value": ""},
            {"key": "entitlementId", "value": ""},
            {"key": "receivableId", "value": ""},
            {"key": "fiscalDocumentId", "value": ""},
            {"key": "sharedEntryId", "value": ""},
            {"key": "invitationId", "value": ""},
            {"key": "subscriptionId", "value": ""},
            {"key": "graphqlWalletId", "value": ""},
            {"key": "tagId", "value": ""},
            {"key": "accountId", "value": ""},
            {"key": "creditCardId", "value": ""},
            {"key": "fakeUuid", "value": "00000000-0000-4000-8000-000000000001"},
            {"key": "alertCategory", "value": "system"},
            {"key": "nonexistentInvitationToken", "value": ""},
            {"key": "suiteProfile", "value": "full"},
            {"key": "enablePrivilegedFlows", "value": "false"},
            {"key": "adminToken", "value": ""},
        ],
    }
    return collection


def main() -> None:
    collection = build_collection()
    COLLECTION_PATH.write_text(
        json.dumps(collection, ensure_ascii=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[postman] wrote {COLLECTION_PATH}")


if __name__ == "__main__":
    main()
