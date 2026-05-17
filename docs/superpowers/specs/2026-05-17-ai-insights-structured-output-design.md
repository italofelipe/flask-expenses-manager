# AI Insights Structured Output Design

## Goal

Make AI spending insights reliably renderable and more useful by enforcing a
structured backend contract, normalizing legacy Markdown JSON, and separating
financial context sent to the LLM.

## Scope

This work covers:

- `auraxis-api` issue #1267: provider contract, response validation, richer
  prompt context, API payload, documentation, and production row normalization.
- `auraxis-web` issue #855: frontend parser tolerance and preferred `items`
  rendering.

It intentionally does not redesign the whole Insights IA page. The UI keeps the
current card rendering and becomes compatible with the improved payload.

## Architecture

The backend remains the source of truth for the LLM contract. It will ask OpenAI
for a schema-constrained object, normalize the result into a list of
`InsightItem` dictionaries, persist JSON-only content, and return both `items`
and the legacy `insights` string. The Web app will prefer `items`, but it will
still parse `insights` or history `content` for old API responses.

## Backend Design

`app/services/llm_provider.py` gets optional structured output support for
OpenAI Chat Completions. The provider accepts an optional JSON schema argument
for `generate_with_usage()`. When present, OpenAI receives
`response_format: {"type": "json_schema", "json_schema": {...}}`.

`app/services/ai_advisory_service.py` owns the spending insight schema and
validation. It parses the provider response, strips code fences only for legacy
or non-structured providers, validates that each item has `type`, `title`, and
`message`, then serializes the list as JSON before saving.

The spending snapshot is expanded to separate paid income, paid expense, and
pending expense. Budgets and goals are included as separate blocks, with an
explicit "no active goals" state.

## Frontend Design

`app/features/ai-insights/contracts/ai-insight.ts` accepts optional `items` in
generation payloads. `mapGeneratedInsight()` prefers `items`; if absent, it
falls back to parsing `insights`. `parseInsightItems()` strips common Markdown
code fences before parsing, so old history rows still render.

Presentation metadata is extended for the insight types already produced by the
backend prompt: `alerta_meta`, `progresso_meta`, `planejamento_meta`,
`orcamento_ultrapassado`, `saude_orcamento_mensal`, `conquista_meta`, and
`savings_rate_gap`.

## Error Handling

If the provider returns malformed output, the backend raises `LLMProviderError`
and returns the existing 500 envelope. No `AIInsight` row is saved. With #1265
deployed, that failed attempt does not consume the daily AI insight quota.

Cached rows return the parsed `items` field when possible. If a cached row is
unrecoverable, the backend should still return the legacy content, but the Web
fallback remains deterministic.

## Tests

Backend tests cover:

- Markdown fenced JSON is normalized to plain JSON.
- Structured provider output returns `items` and persists JSON-only content.
- Malformed provider output raises and does not save an insight.
- Prompt context separates paid and pending transactions.
- No goals are represented explicitly instead of inferred from budgets.

Frontend tests cover:

- fenced JSON parses successfully;
- `items` is preferred over legacy strings;
- legacy JSON still works;
- malformed content still returns fallback;
- new insight types have meaningful presentation metadata.

## Production Operation

Normalize the known malformed row in production after the issue/card setup and
before broad code rollout, because it is a one-row repair and does not change
business logic. Keep `llm_audit_logs` untouched.
