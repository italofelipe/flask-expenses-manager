# AI Insights — Cost Governance, Model, Forecast & Monthly Recap

Reference for the cost/model/limits policy and the automatic monthly recap
(épico #814, issues #1385/#1386).

## Model

The advisory LLM defaults to a **strong model** — `gpt-4o` — for richer, more
assertive insights. Override with `OPENAI_ADVISORY_MODEL`. Pricing per 1M
tokens lives in `LLMResponse.estimated_cost_usd` (`gpt-4o`, `gpt-4o-mini`,
`gpt-4.1`, `gpt-4.1-mini`, claude-haiku).

Cost is bounded by the per-user ceiling + the daily/monthly caps, so a strong
model is used without an automatic downgrade for now (product decision,
2026-05-30). Revisit downgrade-on-budget if usage patterns require it.

## Caps & cost ceiling

| Control | Value | Where |
|---|---|---|
| Daily cap | 1/day per user (BRT) | `AI_DAILY_LIMIT` |
| Monthly cap | 30/month per user (BRT) | `AI_MONTHLY_LIMIT` |
| Per-user cost ceiling | ≤ 50% of plan price ≈ US$2,72/mês | `_enforce_ai_insight_user_cost_budget` |
| Org-wide cost (optional) | env-driven | `AI_INSIGHTS_{DAILY,MONTHLY}_BUDGET_USD` |

Admins (`admin` JWT role) and the monthly recap bypass all of the above. See
[AI-Insights-Rate-Limit](AI-Insights-Rate-Limit.md).

### Environment variables

| Var | Default | Meaning |
|---|---|---|
| `OPENAI_ADVISORY_MODEL` | `gpt-4o` | Advisory model |
| `AI_INSIGHTS_USER_BUDGET_PCT` | `0.5` | Share of plan price as the per-user cap |
| `AI_INSIGHTS_BRL_USD_FX` | `5.50` | BRL→USD rate for the budget conversion |
| `AI_INSIGHTS_DAILY_BUDGET_USD` | (unset) | Optional org-wide daily ceiling |
| `AI_INSIGHTS_MONTHLY_BUDGET_USD` | (unset) | Optional org-wide monthly ceiling |

## Forecast mode (#1385)

When the requested period is entirely in the future (`period_start >
local_today` in the user's timezone — e.g. generating July's insight while it
is still May), generation switches to **forecast mode**: the prompt frames the
snapshot's transactions as *scheduled* commitments/income (the recurring
occurrences materialised by #1384), uses future tense, projects totals/balance,
flags cash-flow risks and how to prepare. The response carries `forecast:
true`.

## Automatic monthly recap (#1386 slice B)

On the 1st of each month a batch consolidates the month that just ended into a
single recap per active user.

- **Entry point:** `scripts/generate_monthly_recaps.py` →
  `generate_monthly_recaps_for_all(reference_date=today)`.
- **Eligibility:** users with ≥1 daily insight in the target month.
- **Idempotent:** users that already have a `monthly` insight for the period
  are skipped.
- **Exempt** from the user daily/monthly caps and cost ceiling (runs off the
  rate-limited endpoint; `monthly` is exempt from the cost guard).
- Reuses `create_monthly_report_run` + `process_monthly_report_run`, which
  aggregate the month's daily insights + the previous monthly recap and email a
  deep link.

### Cron (production)

Schedule on the 1st of each month (BRT 06:00 → 09:00 UTC):

```cron
0 9 1 * * cd /app && python scripts/generate_monthly_recaps.py >> /var/log/auraxis/monthly_recap.log 2>&1
```

Mirror the install pattern of the recurring-transactions cron
(`scripts/generate_recurring_transactions.py`). The job is safe to re-run
(idempotent) and logs `monthly_recap.batch` start/done lines.
