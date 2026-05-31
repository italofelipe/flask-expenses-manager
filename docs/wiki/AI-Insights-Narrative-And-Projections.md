# AI Insights — Transactions Narrative & Projections

How the `transactions` dimension produces an assertive, grounded narrative
(épico #814, issue #1394).

## Target format

The `transactions` item reads as a flowing paragraph that weaves together:
1. **The day's concrete transactions** — name, amount and status, from
   `transactions.sample` / `transactions.changes_since_last_generation`.
2. **The month position** — how much came in/out and whether the month's
   responsibilities are covered, from `current_period.paid` /
   `current_period.commitments`.
3. **Same-day-last-month comparison** — a concrete figure from
   `comparisons.same_day_previous_month`.
4. **A forward projection** — "if you save X and invest Y, in 3/6/12 months
   ≈ Z", citing **only** `projections.*`.

## Why projections are computed in the backend

The evidence validator (`insight_evidence_validator.py`) drops any insight item
whose `evidence` does not point at a known snapshot key. The model therefore
**cannot invent** projected figures — they must exist in the snapshot. The
`projections` block is computed deterministically in
`financial_insight_context_builder.py` and the prompt forbids the model from
doing its own math.

## `projections` block

Attached to the daily snapshot (`build_daily`). Horizons: **3, 6, 12 months**.

- `rate_basis`: `observed` (value-weighted `annual_rate` across wallet items),
  `cdi_fallback` (uses `wallet.benchmark.cdi_monthly_pct` when there are no
  positions), or `none`.
- `monthly_rate_pct`: the monthly rate applied.
- `wallet.horizon_<h>m`: lump-sum future value of `wallet.total_value`
  (omitted when total is zero).
- `goals[i].horizon_<h>m_observed` / `_required`: goal value at the observed
  and required monthly pace.
- `combined_scenario.horizon_<h>m`: "save X (= goal `required_monthly_pace`) +
  invest Y (= positive `current_period.paid.balance`)" — goal contributions plus
  the future value of monthly investments at `rate_basis`.

Blocks with no data (no goal / no wallet) are omitted — never fabricated.

## Evidence whitelist

The `transactions` dimension accepts `transactions`, `comparisons`,
`current_period.paid`/`.commitments`, plus `goals`, `wallet` and `projections`
(the narrative legitimately references them). See `insight_evidence_validator.py`.

## Decisions (2026-05-30)

- Projection rate = **observed wallet return** (CDI fallback). Horizons 3/6/12m.
- Narrative scope = the `transactions` dimension (the `general` panorama may
  also reference any known prefix).
