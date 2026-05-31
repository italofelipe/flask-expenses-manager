# AI Insights — Feedback / Rating Loop

User feedback on generated insights, feeding continuous prompt improvement
(épico #814, issue #1387).

## What it captures

Per (user, insight): four 0–5 ratings — **relevance**, **truthfulness**,
**depth**, **usefulness** — plus an optional free-text **comment**. One row per
(user, insight); re-submitting **updates** the existing feedback (upsert).

Stored in `ai_insight_feedback` (`AIInsightFeedback` model). A user may only
rate **their own** insights (ownership enforced server-side; 404 otherwise).

## REST

`POST /ai/insights/<insight_id>/feedback` (JWT required; no Premium gate — any
user who owns the insight can rate it).

```json
{ "relevance": 5, "truthfulness": 4, "depth": 4, "usefulness": 5, "comment": "Muito útil" }
```

- `201` — feedback recorded (returns the stored row).
- `400` `VALIDATION_ERROR` — rating outside 0–5 or malformed body.
- `404` `AI_INSIGHT_NOT_FOUND` — insight does not exist or is not the caller's.

## GraphQL (parity)

```graphql
mutation {
  submitAiInsightFeedback(
    insightId: "<uuid>", relevance: 5, truthfulness: 4, depth: 4, usefulness: 5, comment: "Muito útil"
  ) { ok relevance truthfulness depth usefulness comment }
}
```

Same validation/ownership rules (`VALIDATION_ERROR` / `NOT_FOUND`).

## Continuous improvement

`get_insight_feedback_aggregate()` returns the count and the average per rating
dimension across all feedback. This is the signal for refining the insight
prompts over time (e.g. low `truthfulness` → tighten evidence/anti-hallucination
instructions; low `depth` → enrich the narrative/projection guidance).

Implementation: `app/application/services/ai_insight_feedback_service.py`.
