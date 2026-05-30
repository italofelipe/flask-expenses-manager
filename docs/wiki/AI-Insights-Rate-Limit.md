# AI Insights Rate Limit

Manual AI insights are limited per user, on the BRT calendar, to:

- **1 successful generation per day** (`AI_DAILY_LIMIT`); and
- **30 successful generations per month** (`AI_MONTHLY_LIMIT`).

> The automatic end-of-month recap is **not** subject to these caps — it runs
> via a batch job, not the rate-limited endpoint. See
> [AI-Insights-Cost-And-Recap](AI-Insights-Cost-And-Recap.md).

## Admin bypass

Requests whose JWT carries the `admin` role bypass **both** caps and the cost
ceiling entirely (`request_is_admin()` in `app/middleware/ai_rate_limit.py`).
This lets the team exercise the feature end-to-end without consuming a real
user's allowance. Admin generations still log cost to `LLMAuditLog`.

## What Counts

A request consumes one daily slot only when all of the following are true:

- the user is Premium and passes the entitlement gate;
- the endpoint returns a 2xx response;
- the response represents a new LLM generation;
- the response is not served from the persisted insight cache.

## What Does Not Count

The daily counter is not consumed by:

- unauthenticated requests;
- users without the `advanced_simulations` entitlement;
- validation errors;
- OpenAI/Anthropic provider errors, including quota and invalid-key failures;
- internal errors before a usable insight is returned;
- cached spending insights returned with `cached=true`.

This avoids penalizing users for infrastructure, provider, or configuration
failures where Auraxis did not produce a new AI insight.

## Cost Circuit Breaker

Manual financial insight generation also checks USD budgets before calling the
LLM provider. Two layers:

1. **Org-wide (optional, env-driven):** `AI_INSIGHTS_DAILY_BUDGET_USD` /
   `AI_INSIGHTS_MONTHLY_BUDGET_USD`. Empty/zero/negative disables the layer.
2. **Per-user (#1386):** a user's month-to-date AI cost must never exceed
   **50% of the Premium subscription price** (R$29,90, ADR-669). The limit is
   `price × AI_INSIGHTS_USER_BUDGET_PCT (default 0.5) ÷ AI_INSIGHTS_BRL_USD_FX
   (default 5.50)` ≈ **US$2,72/mês**. Source of truth is
   `LLMAuditLog.estimated_cost_usd` filtered by `user_id`.

Both layers cover the `financial_insights_daily/weekly/monthly` endpoints. When
spend is at or above a limit, generation is blocked before GPT is called and
the API returns HTTP `429` with error code `AI_INSIGHT_BUDGET_EXCEEDED`
(per-user scope: `user_monthly`).

Exemptions: cached insights (no new cost), admin requests, and the **monthly
recap** (`period_type=monthly`, a guaranteed deliverable) are not blocked by
the cost ceiling. Their cost is still logged.

See [AI-Insights-Cost-And-Recap](AI-Insights-Cost-And-Recap.md) for the model
choice, the full env reference, and the recap cron.

## Response Headers

Successful and failed pass-through responses include `X-AI-Calls-Remaining`
(daily) and `X-AI-Calls-Remaining-Month` (monthly) when they reach the AI
limit middleware. Requests blocked by a quota return:

- HTTP `429`;
- error code `AI_DAILY_LIMIT_EXCEEDED` (daily) or `AI_MONTHLY_LIMIT_EXCEEDED`
  (monthly);
- `Retry-After` with seconds until the next BRT day (daily) or first day of
  next month (monthly);
- `X-AI-Calls-Remaining: 0` (and `X-AI-Calls-Remaining-Month: 0` for the
  monthly cap).
