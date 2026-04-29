# Simulations Persistence — Backend Implementation Guide

> Status: Planned · Decision: ADR `simulations_canonical_persistence.md` (platform) /
> DEC-196 · Date: 2026-04-29

## Scope

A single canonical endpoint persists simulations from any of the 38+ Auraxis
calculators (juros compostos, CDB/LCI/LCA, salário líquido, …). The backend is a
pure persistor — calculation lives in the client.

This page is the implementation guide for `auraxis-api`. The product-level
architecture is documented at `auraxis-platform/docs/wiki/Simulations-Persistence.md`.

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/simulations` | Save a new simulation. |
| `GET` | `/simulations` | List simulations owned by current user (paginated). |
| `GET` | `/simulations/{id}` | Get a single simulation owned by current user. |
| `DELETE` | `/simulations/{id}` | Delete a simulation owned by current user. |

GraphQL parity (Ariadne) is **mandatory**:

```graphql
type Mutation {
  saveSimulation(input: SaveSimulationInput!): Simulation!
  deleteSimulation(id: ID!): Boolean!
}

type Query {
  simulations(page: Int = 1, perPage: Int = 20): SimulationConnection!
  simulation(id: ID!): Simulation
}
```

## Request schema (REST + GraphQL share the shape)

```jsonc
{
  "tool_id": "compound-interest",
  "rule_version": "2026.04",
  "inputs":  { /* JSON object, opaque to backend */ },
  "result":  { /* JSON object, opaque to backend */ },
  "metadata": {
    "label": "Cenário 1",
    "notes": "..."
  }
}
```

### Pydantic / Marshmallow validation rules

Use Marshmallow (project convention). The schema:

| Field | Type | Constraints |
|-------|------|-------------|
| `tool_id` | string | required; must be in `TOOLS_REGISTRY` (allowlist) |
| `rule_version` | string | required; 1–32 chars; ASCII printable |
| `inputs` | object | required; non-null JSON object (not array, not scalar) |
| `result` | object | required; non-null JSON object (not array, not scalar) |
| `metadata` | object | optional; non-null JSON object if present |

Body size hard cap **16 KB** enforced before parsing (Flask `MAX_CONTENT_LENGTH`
override on this route). Larger payload → `413 Payload Too Large`.

### `TOOLS_REGISTRY`

Static Python set (or frozen dataclass) listing every accepted `tool_id`. Mirrors
`auraxis-app/features/tools/services/tools-catalog.ts`.

```python
# app/simulations/tools_registry.py
TOOLS_REGISTRY: frozenset[str] = frozenset({
    "installment-vs-cash",
    "compound-interest",
    "cdb-lci-lca",
    "salary-net-clt",
    # ...all 38 tool_id values
})
```

A CI parity check compares the registry against the app's catalog and fails the
build if they diverge. (Implemented in PR — script reads both files and diffs the
sets.)

## Authorization & ownership

- Auth required on every endpoint (JWT middleware).
- `user_id` is **always** derived from the authenticated principal — never accepted
  in the request body.
- `GET /simulations`, `GET /simulations/{id}`, `DELETE /simulations/{id}` filter by
  `user_id == current_user.id`. Other users' rows yield `404 Not Found` (not 403,
  to avoid leaking existence).

## Rate limiting

`POST /simulations`: **60 saves / minute / user** (Redis-backed counter using the
existing rate-limit middleware). Excess requests return `429 Too Many Requests`
with `Retry-After`.

## Database

Reuse the existing `simulations` table created for installment-vs-cash. If columns
named for that domain exist (e.g., `cash_price`), generalize them to `inputs` and
`result` jsonb in a migration that:

1. adds `inputs` (jsonb), `result` (jsonb), `metadata` (jsonb nullable),
   `rule_version` (text), `tool_id` (text) if missing;
2. backfills existing installment-vs-cash rows into the new shape;
3. drops legacy columns only after parity is validated in production.

If the current shape is already generic (likely — the existing
`InstallmentVsCashSavedSimulationDto` looks normalized), the migration is a no-op
and only the index below is needed:

```sql
CREATE INDEX IF NOT EXISTS idx_simulations_user_tool_created
  ON simulations (user_id, tool_id, created_at DESC);
```

## Pagination

`GET /simulations`:

- `page` (default 1, min 1)
- `per_page` (default 20, max 50)
- Response envelope mirrors existing list endpoints:
  ```json
  {
    "items": [...],
    "page": 1,
    "per_page": 20,
    "total_pages": 5,
    "total_items": 87
  }
  ```

Optional filters:

- `tool_id=<id>` — restrict to one tool.
- `from=<iso8601>` / `to=<iso8601>` — date range on `created_at`.

## Error semantics

| HTTP | Reason |
|------|--------|
| 200 OK | GET success |
| 201 Created | POST success |
| 204 No Content | DELETE success |
| 401 Unauthorized | Missing or invalid JWT |
| 404 Not Found | id does not exist or is not owned by current user |
| 413 Payload Too Large | body > 16 KB |
| 422 Unprocessable Entity | validation failure (unknown `tool_id`, malformed payload, etc.) |
| 429 Too Many Requests | rate limit exceeded |

## OpenAPI / Postman

- Update `openapi.json` snapshot via `python3 scripts/export_openapi_snapshot.py`
  after the routes land. The snapshot is consumed by the public Scalar portal and
  by `auraxis-web` / `auraxis-app` contracts packs.
- Update the Postman collection (private workspace `Auraxis API`) using the
  Postman MCP tools or `make export-postman` (verify exact target).
- Add request examples for: success, validation error, rate-limit hit.

## Tests

Required test scope (matches Definition of Done for this repo):

- **Unit (services/repository):** registry validation, rule_version trim, jsonb
  size cap, ownership filter, pagination math, rate-limit accounting.
- **Integration (controllers + GraphQL):** happy path, malformed payload, unknown
  `tool_id`, payload too large, unauthorized, foreign user attempting access,
  rate-limit overflow, list pagination, list filtering, delete cascade behavior.
- **Contract:** snapshot of OpenAPI matches checked-in fixture; GraphQL schema SDL
  diff guarded.

Coverage threshold: ≥ 85% (project standard).

## Migration / rollout coordination

This endpoint must ship **before** the consumer PRs in `auraxis-web` and
`auraxis-app`. Coordinate with the issues:

- `auraxis-web` issue (link TBD) — adopts generic save flow + UX prompt.
- `auraxis-app` issue (link TBD) — implements lote B (juros compostos +
  CDB/LCI/LCA) using the new endpoint.

`installment-vs-cash` continues to work via its existing endpoints during the
transition; once the generic endpoint is GA, the bespoke save endpoint can be
deprecated in a follow-up (out of scope for this PR).

## See also

- Platform ADR: `.context/adr/simulations_canonical_persistence.md`
- Platform Wiki: `docs/wiki/Simulations-Persistence.md`
- Decision log: DEC-196
