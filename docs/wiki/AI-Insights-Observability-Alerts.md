# AI Insights — Observability & Alerts

Reference for the run/cost/quality/governance metrics emitted by the AI insight
pipeline and the alerts to configure on them (épico #814, issue #1314).

Metrics are Prometheus instruments defined in
`app/extensions/prometheus_metrics.py` and scraped at `/ops/metrics`. Structured
logs are emitted by `app/services/ai_insight_runs.py` and
`app/services/insight_evidence_validator.py`.

## Metrics

| Metric | Type | Labels | Emitted where |
|---|---|---|---|
| `auraxis_ai_insight_runs_total` | Counter | `status`, `period_type` | every `AIInsightRun` state entry — `create_ai_insight_run` (previewed) + `transition_ai_insight_run_status` (generated/cached/blocked) + purge (purged) |
| `auraxis_ai_insight_cost_usd_total` | Counter | `period_type` | on `generated` runs, summing `estimated_cost_usd` |
| `auraxis_ai_insight_rejections_total` | Counter | `reason` | `filter_valid_items` per rejected item |
| `auraxis_ai_insight_truncated_total` | Counter | `period_type` | `create_ai_insight_run` when the snapshot was truncated |
| `auraxis_ai_insight_data_quality_domains` | Histogram | `period_type` | `create_ai_insight_run`; observes domains present (0–6) |
| `auraxis_ai_insight_runs_purged_total` | Counter | — | `purge_expired_ai_insight_runs` |
| `auraxis_ai_insight_generated_total` | Counter | `period_type`, `dimension` | (pre-existing) per generated dimension |
| `auraxis_ai_insight_tokens` | Histogram | `period_type` | (pre-existing) tokens per generation |
| `auraxis_ai_insight_snapshot_bytes` | Histogram | `period_type`, `truncated` | (pre-existing) snapshot size post-truncation |

> `runs_total` counts **state entries**, not distinct runs: a single run that
> goes `previewed → generated` increments both. This lets you derive rates such
> as rejection-rate = `blocked / previewed` and conversion = `generated /
> previewed`.

### `rejections_total` reason values

Stable, bounded labels from `insight_evidence_validator`: `invalid_dimension`,
`missing_evidence`, `empty_evidence`, `unknown_path_prefix`,
`dimension_evidence_mismatch`.

## Structured logs (no PII)

Run-scoped logs carry only auditable, non-PII fields — `run_id`,
`snapshot_hash`, `period_type`, `period`, `status`, `tokens`, `cost_usd`,
`truncated`, `domains_present`. The raw snapshot and prompt are **never**
logged. PII in free text is additionally scrubbed before persistence by
`sanitize_audit_snapshot` (emails/CPF/long numbers → placeholders; id-like keys
dropped).

- `ai_insight.run.created …` — on persistence (`logging.INFO`)
- `ai_insight.run.transition …` — on each status change
- `ai_insight.run.purged count=… …` — on retention purge
- `ai_advisory.evidence_validation.rejected …` — per rejected item (`WARNING`)

## Alerts

Configure these against the metrics above (thresholds are starting points —
tune with production baselines).

| Alert | Condition (PromQL sketch) | Why |
|---|---|---|
| **High cost** | `increase(auraxis_ai_insight_cost_usd_total[1h]) > 1.0` (US$/h) or daily sum approaching `AI_INSIGHTS_DAILY_BUDGET_USD` | LLM spend running hot before the org budget gate trips |
| **High rejection rate** | `sum(rate(auraxis_ai_insight_rejections_total[15m])) / sum(rate(auraxis_ai_insight_runs_total{status="previewed"}[15m])) > 0.3` | LLM producing evidence-inconsistent items → prompt/model regression |
| **Frequent truncation** | `sum(rate(auraxis_ai_insight_truncated_total[1h])) / sum(rate(auraxis_ai_insight_runs_total{status="previewed"}[1h])) > 0.25` | Snapshots consistently exceeding the byte cap → context loss; revisit `MAX_SNAPSHOT_BYTES` or snapshot shape |
| **Purge failure / stall** | `increase(auraxis_ai_insight_runs_purged_total[36h]) == 0` while expired rows exist | Retention job not running → LGPD/retention risk (snapshots kept past window) |
| **Low data quality** | `histogram_quantile(0.5, rate(auraxis_ai_insight_data_quality_domains_bucket[6h])) < 2` | Insights generated on sparse data → low-value output |
| **Generation failures** | sustained `previewed` with no matching `generated`/`cached`/`blocked` | runs stuck mid-lifecycle (LLM errors / crashes) |

The purge job is the monthly recap cron's sibling; if `runs_purged_total` is
flat, check the retention scheduler before assuming zero expired rows.

## Related

- [AI-Insights-Cost-And-Recap](AI-Insights-Cost-And-Recap.md) — cost ceiling & caps
- [AI-Insights-Rate-Limit](AI-Insights-Rate-Limit.md) — per-user daily/monthly caps
- [AI-Insights-Structured-Output](AI-Insights-Structured-Output.md) — evidence contract
