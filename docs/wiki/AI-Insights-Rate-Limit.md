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

## Response Headers

Successful and failed pass-through responses include `X-AI-Calls-Remaining`
when they reach the AI daily-limit middleware. Requests blocked by the quota
return:

- HTTP `429`;
- error code `AI_DAILY_LIMIT_EXCEEDED`;
- `Retry-After` with seconds until the next BRT day;
- `X-AI-Calls-Remaining: 0`.
