# GraphQL Security Runbook

## Complexity limit

Every GraphQL query is scored against a complexity budget before execution.
The budget is configured via environment variables:

| Env var | Default | Description |
|---------|---------|-------------|
| `GRAPHQL_MAX_QUERY_BYTES` | 20 000 | Maximum request body size in bytes |
| `GRAPHQL_MAX_DEPTH` | 8 | Maximum AST nesting depth |
| `GRAPHQL_MAX_COMPLEXITY` | 300 | Maximum weighted field count |
| `GRAPHQL_MAX_OPERATIONS` | 3 | Maximum operations per document |
| `GRAPHQL_MAX_LIST_MULTIPLIER` | 50 | Multiplier for list-shaped arguments |
| `GRAPHQL_ALLOW_INTROSPECTION` | `false` | Enable schema introspection (true in DEBUG) |

## Per-field complexity weights

Individual fields can be assigned a higher base cost to reflect that their
resolvers make external HTTP calls or expensive DB aggregates.

**Default weights** (in `app/graphql/security.py → _DEFAULT_FIELD_WEIGHTS`):

| Field | Weight | Reason |
|-------|--------|--------|
| `investmentValuation` | 10 | Calls BRAPI market-data API per request |
| `portfolioValuation` | 10 | Calls BRAPI market-data API per request |
| `portfolioValuationHistory` | 8 | Calls BRAPI + pagination |
| `billingPlans` | 5 | Calls billing provider |
| `dashboardOverview` | 3 | Multiple DB aggregate queries |
| `transactionDashboard` | 3 | Multiple DB aggregate queries |
| All other fields | 1 (default) | Standard resolver |

### How complexity is calculated

For each field: `cost = base_weight * (1 + child_complexity * list_multiplier)`.
The budget covers the entire operation. A query with three weighted fields
accumulates their costs together.

### Override via environment variable

Set `GRAPHQL_FIELD_WEIGHTS_JSON` to a JSON object to replace the default table:

```bash
GRAPHQL_FIELD_WEIGHTS_JSON='{"myExpensiveField": 20, "cheapField": 1}'
```

When the env var is absent or malformed, the compiled defaults apply.

## Auth policy

Every mutation and non-public query **must** call `get_current_user_required()`
as the first line, OR be added to the explicit public allowlist in
`app/graphql/authorization.py`.

A parameterized regression test (`tests/test_graphql_auth_everywhere.py`)
enumerates all operations at runtime and asserts each non-allowlisted operation
rejects unauthenticated requests with `extensions.code = UNAUTHORIZED`.

Adding to the allowlist requires deliberate justification in the PR description.

## Playground (dev/staging)

A self-contained GraphiQL 3 interface is available at `GET /graphql/playground`
when the `ENABLE_GRAPHQL_PLAYGROUND` feature flag is enabled AND the caller has
an admin JWT role. The endpoint is always registered but returns 404 by default.

Enable for a session:
```bash
# via feature-flags admin API
curl -X POST /admin/feature-flags \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"name": "ENABLE_GRAPHQL_PLAYGROUND", "status": "enabled"}'
```

## Introspection

Schema introspection (`__schema`, `__type`) is disabled in production.
It is automatically enabled when `FLASK_DEBUG=true` (local dev), or by
setting `GRAPHQL_ALLOW_INTROSPECTION=true` explicitly.

Do **not** enable introspection in production — it exposes the full schema
surface to potential attackers.
