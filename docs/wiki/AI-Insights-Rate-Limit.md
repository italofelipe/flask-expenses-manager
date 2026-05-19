# AI Insights Rate Limit

Manual AI insights are limited to 2 successful generations per user per BRT
calendar day.

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

Manual financial insight generation also checks the configured USD budget
before calling the LLM provider:

- `AI_INSIGHTS_DAILY_BUDGET_USD`
- `AI_INSIGHTS_MONTHLY_BUDGET_USD`

Empty, missing, zero, or negative values disable the corresponding budget.
When a positive limit is configured, the source of truth is
`LLMAuditLog.estimated_cost_usd` for `financial_insights_daily`,
`financial_insights_weekly`, and `financial_insights_monthly`. If the current
daily or monthly spend is already at or above the configured limit, generation
is blocked before GPT is called and the API returns HTTP `429` with error code
`AI_INSIGHT_BUDGET_EXCEEDED`.

Cached insights are returned before the budget check because they do not
generate new LLM cost. Admin preview and dossier export are also unaffected:
they never call the LLM provider and do not consume budget.

## Response Headers

Successful and failed pass-through responses include `X-AI-Calls-Remaining`
when they reach the AI daily-limit middleware. Requests blocked by the quota
return:

- HTTP `429`;
- error code `AI_DAILY_LIMIT_EXCEEDED`;
- `Retry-After` with seconds until the next BRT day;
- `X-AI-Calls-Remaining: 0`.
