# ADR-0006: AI Insight Dimensions + Snapshot Observability

Status: accepted
Date: 2026-05-18
Refs: #1287 #1288 #1289 (Sprints 3 + 5 of MVP-3); supersedes parts of #1271

## Context

MVP-3 (Hub de Cartões + Insights Globais) requires every AI insight item to
declare which surface it belongs to so the frontend can filter contextually
(transactions page, credit cards page, goals page, budgets page) while the
`/insights` hub shows everything grouped. We also need observability on token
spend, snapshot size and dimension distribution to keep LLM cost predictable.

## Decision

### 1. Dimension is a closed enum with a `general` fallback

```python
INSIGHT_DIMENSIONS = ("general", "transactions", "credit_cards", "goals", "budgets")
```

- LLM response schema requires `dimension` per item, validated against this
  enum (strict mode).
- `_coerce_financial_insight_item` accepts items missing `dimension` and
  defaults to `general`. This handles AIInsight rows persisted before MVP-3
  (Sprint 3 cutover) so the history endpoint never breaks.
- Invalid explicit dimensions raise `LLMProviderError` — silent acceptance
  would let the model leak the enum surface area over time.

### 2. Quota is global per user, not per dimension

- 2 generations per day per user (Premium). Decision recorded in the wiki
  (2026-05-17) and re-affirmed in chat.
- A single generation may contain items across multiple dimensions; that's
  one quota unit.
- Rationale: per-dimension quotas multiply LLM cost by 5× without giving
  users meaningfully better targeting. Users self-prioritise via the surface
  they trigger generation from.

### 3. Snapshot has a 12 KiB byte cap with deterministic truncation

`MAX_SNAPSHOT_BYTES = 12 * 1024` (overridable via `AI_SNAPSHOT_MAX_BYTES`).

When the JSON-serialized snapshot exceeds the cap, `truncate_snapshot()`
reduces large lists in this order:

1. `transactions.items` → top 10 expense + top 5 income (by amount).
2. `daily_series` → last 7 days.
3. `credit_cards` → drop cards with zero/None utilization.
4. `categories.top_expense_categories` → keep top 5.

Always preserved: `schema_version`, `period_type`, `period`, `current_period`,
`comparisons`, `data_quality`.

A structured warning is logged on truncation (`ai_advisory.snapshot.truncated`).

### 4. Persistence: `AIInsight.metadata_json` (nullable Text)

Single nullable JSON-in-Text column on `ai_insights`. Stores per-generation
observability metadata:

```json
{
  "snapshot_version": "financial_insight_snapshot.v1",
  "context_hash": "sha256:abc...",
  "comparisons_available": ["yesterday", "previous_week", "same_day_previous_month"],
  "dimensions_present": ["general", "credit_cards"],
  "snapshot_bytes_original": 14823,
  "snapshot_bytes_final": 11942,
  "truncated": true,
  "dropped_sections": ["transactions.items", "daily_series"]
}
```

Legacy rows (pre-cc2 migration) keep `metadata_json = NULL`. Callers read via
`AIInsight.metadata_dict` property (transparent JSON encode/decode).

**Why Text JSON, not dedicated columns**: keeps the migration trivial (one
nullable Text column), maintains SQLite parity for tests, and avoids
hot-loop schema churn as the metadata vocabulary evolves. Cost: no SQL
filtering on inner fields. We don't need that — observability is consumed
via Prometheus, not SQL.

### 5. Prometheus counters and histograms

Added in `app/extensions/prometheus_metrics.py`:

| Metric | Type | Labels | Purpose |
|---|---|---|---|
| `auraxis_ai_insight_generated_total` | Counter | `period_type`, `dimension` | Generation volume by surface |
| `auraxis_ai_insight_tokens` | Histogram | `period_type` | Token spend distribution |
| `auraxis_ai_insight_snapshot_bytes` | Histogram | `period_type`, `truncated` | Snapshot size before/after truncate gate |

Recorded once per non-cached generation via `record_ai_insight_generated()`.
Fire-and-forget — failures here never abort the user-facing flow.

## Consequences

### Positive

- Frontend can render contextual dashboards (Sprint 4 by Codex) by filtering
  on `dimension` without consulting the full snapshot.
- LLM cost stays bounded: snapshot capped + token histogram surfaces outliers.
- Single migration (cc2) keeps deployment simple.
- Adding new comparison periods or sections later doesn't require migrations
  — the JSON metadata grows without schema churn.

### Negative / accepted trade-offs

- `metadata_json` is opaque to SQL — Grafana dashboards rely on Prometheus,
  not on querying the column.
- Closed dimension enum requires a code change + migration of LLM prompt
  whenever a new surface is added (acceptable: roadmap is bounded).
- Per-dimension counters can multiply storage rows in long-running Prometheus
  retention. Bucket cardinality is bounded at 5 dimensions × 3 period_types
  = 15 series. Negligible.

## Alternatives considered

- **Open-ended `tags: list[str]`** on items instead of closed enum. Rejected:
  the frontend needs a fixed set of buckets to render UI; open tags push
  routing complexity to the client.
- **Per-dimension quota** (2x/day × 5 dimensions = 10 calls/day). Rejected:
  5× cost without obvious user value. Revisit if users complain about
  forced prioritisation.
- **Dedicated columns for `snapshot_bytes_original`, etc.** Rejected: each
  new metric becomes a migration. JSON-in-Text gives evolution room.
- **Truncate by simply chopping the JSON string**. Rejected: produces invalid
  JSON and confuses the LLM. Structured reduction preserves semantics.

## Related ADRs

- ADR-0002 GraphQL ownership (REST canonical for writes — applies to the
  REST-first POST /ai/insights/generate)
- ADR-0005 AI insight persistence model

## Verification

- Unit tests for `truncate_snapshot()` cover input below cap, transaction
  trim path, daily_series trim path (`tests/test_ai_insight_observability.py`).
- Integration test confirms `metadata_json` populated + counter recorded on
  every generation.
- Prometheus scrape returns the new metrics (smoke check via `/metrics`).
