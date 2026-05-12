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

## REST vs GraphQL ownership policy

GraphQL in Auraxis follows the **read-heavy, REST-primary** model defined in ADR-0002 and
extended by ADR-0004.

### Rules

| Operation type | Canonical surface |
|---|---|
| **Domain CRUD** (create/update/delete entities) | REST (`/transactions`, `/goals`, `/wallet`, etc.) |
| **Complex reads + aggregations** (dashboard, multi-join queries) | GraphQL queries |
| **Auth operations** (login, register, reset password) | GraphQL mutations (no REST equivalent) |
| **Composite cross-domain mutations** (simulations) | GraphQL mutations (no REST equivalent) |

### Deprecated mutations

All domain CRUD mutations remain in the schema for backward compatibility but carry a
`deprecation_reason` pointing to the REST equivalent. They will be removed in a future ADR.

See `docs/adr/0002-graphql-ownership.md` and `docs/adr/0004-graphql-ownership-scope-completion.md`.

### Adding a new mutation

Before adding a GraphQL mutation, ask: **does a REST endpoint for this already exist?**

- Yes → add `deprecation_reason` pointing to the REST endpoint, or don't add the mutation.
- No → add the mutation (and also add the REST endpoint for parity).

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

## GraphQL Codegen pipeline (auraxis-web + auraxis-app)

### Source of truth

`schema.graphql` committed in this repo (`repos/auraxis-api/schema.graphql`) is the
canonical SDL used by every consumer. It is auto-regenerated from the Python source
via `scripts/export_graphql_docs.py --source runtime` and validated on every PR by
the `graphql-breaking-change.yml` workflow.

### How consumer types are generated

Both `auraxis-web` and `auraxis-app` use `@graphql-codegen/cli` to generate
TypeScript types from `schema.graphql`. Each consumer repo has a `codegen.ts` config
at its root.

| Consumer | Config file | Output |
|----------|-------------|--------|
| `auraxis-web` | `codegen.ts` | `app/shared/types/generated/graphql.ts` |
| `auraxis-app` | `codegen.ts` | `shared/types/generated/graphql.ts` |

Plugins used: `typescript` (schema types) + `typescript-operations` (operation types) +
`typed-document-node` (typed DocumentNode objects, compatible with TanStack Query).

### Full lifecycle: backend schema change → client types update

1. **Modify Python GraphQL schema** in `app/graphql/` (queries, mutations, types).
2. **Regenerate SDL** locally:
   ```bash
   python scripts/export_graphql_docs.py --source runtime
   ```
   This updates `schema.graphql`, `graphql.introspection.json`, and `graphql.operations.manifest.json`.
3. **Commit the updated `schema.graphql`** in auraxis-api (required — CI fails otherwise).
4. In each consumer repo, **regenerate client types**:
   ```bash
   # auraxis-web (requires schema available at ../auraxis-api/schema.graphql or GRAPHQL_SCHEMA_PATH)
   pnpm codegen

   # auraxis-app
   npm run codegen
   ```
5. **Commit the updated `graphql.ts`** in the consumer repo.
6. CI runs `codegen:check` in each consumer: regenerates types and fails if `git diff` shows changes.

### CI enforcement

Each consumer CI pipeline (`.github/workflows/ci.yml`) has a `graphql-codegen` job that:
1. Fetches `schema.graphql` via `GRAPHQL_SCHEMA_PATH` (set to the raw GitHub URL of `master`).
2. Runs `pnpm codegen:check` / `npm run codegen:check`.
3. Fails if the regenerated types differ from what is committed.

This means: **if you change the schema without updating the committed `graphql.ts` in consumers,
the consumer CI will fail**.

### Developer workflow (local)

```bash
# In auraxis-platform (monorepo layout), ../auraxis-api/schema.graphql is on the path.
# Run from the consumer repo root:

# auraxis-web
cd repos/auraxis-web
pnpm codegen        # regenerate types
pnpm codegen:check  # regenerate + git diff (CI-equivalent)

# auraxis-app
cd repos/auraxis-app
npm run codegen
npm run codegen:check
```

To override the schema source (e.g. testing with a local non-committed schema):
```bash
GRAPHQL_SCHEMA_PATH=/path/to/schema.graphql pnpm codegen
```
