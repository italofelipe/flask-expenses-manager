# AI Insights Structured Output

## Incident Summary

On 2026-05-17, `GET /ai/insights/spending` returned HTTP 200 for a Premium
user, but the Web UI rendered the fallback message:

> Insight indisponível. Não conseguimos interpretar este insight agora.

The API response had `cached=true`, so that specific request did not call
OpenAI. The real OpenAI call had already happened and had persisted a daily
`AIInsight` row.

Production evidence for user `ee8d33ca-0ac0-41cc-95bd-c4be49cbcbd5`:

- `ai_insights.id`: `5508449c-1955-4382-99a7-209092a70d44`
- `period_label`: `2026-05-17`
- `model`: `gpt-4o-mini-2024-07-18`
- `tokens_used`: `567`
- `llm_audit_logs.latency_ms`: `3060`
- persisted content: Markdown fenced JSON, starting with ```` ```json ````.

## Root Causes

1. The backend asked for JSON only through prompt text. It did not use OpenAI
   Structured Outputs or `response_format`.
2. The backend persisted raw LLM text in `ai_insights.content`.
3. The Web parser expected pure JSON and called `JSON.parse()` directly.
4. The prompt asked for three cards, not a detailed report.
5. The spending snapshot only included `paid` transactions. Pending expenses
   were invisible to the model.
6. Budgets and goals were not clearly separated in the prompt, allowing the
   model to treat an overall budget named "Comprar carro novo" as a goal.

## Contract

The spending insight endpoint must return both legacy and structured fields:

```json
{
  "success": true,
  "message": "Insights de gastos gerados com sucesso",
  "data": {
    "insights": "[{\"type\":\"...\",\"title\":\"...\",\"message\":\"...\"}]",
    "items": [
      {
        "type": "saude_financeira",
        "title": "Resumo financeiro",
        "message": "Mensagem acionável em português brasileiro."
      }
    ],
    "month": "2026-05",
    "model": "gpt-4o-mini-2024-07-18",
    "tokens_used": 567,
    "cost_usd": 0.00000276,
    "cached": false
  }
}
```

`insights` remains for backward compatibility, but must be a valid JSON string
without Markdown fences. `items` is the preferred field for new clients.

## Period-Aware History Contract

`POST /ai/insights/generate` persists period-aware insights as canonical JSON
with `summary`, `items[]` and `metadata`. `GET /ai/insights/history` must expose
those fields directly so Web/App clients do not parse `content` themselves:

```json
{
  "id": "uuid",
  "content": "{\"summary\":\"Resumo\",\"items\":[],\"metadata\":{...}}",
  "insight_type": "weekly",
  "period_type": "weekly",
  "period_label": "2026-W20",
  "summary": "Resumo",
  "items": [],
  "context_schema_version": "financial_insight_snapshot.v1",
  "context_hash": "sha256-do-snapshot-sanitizado"
}
```

Legacy rows that contain a JSON array remain readable: history returns the
array as `items` and leaves `summary`, `context_schema_version` and
`context_hash` as `null`.

## OpenAI Output Rule

For OpenAI Chat Completions, use Structured Outputs with
`response_format.type=json_schema` and `strict=true` when supported by the
configured model. If a provider response cannot be parsed into the expected
schema, the service must raise `LLMProviderError` before saving an `AIInsight`.

The current default model, `gpt-4o-mini`, supports Structured Outputs through
the deployed snapshot `gpt-4o-mini-2024-07-18`.

## Financial Context Rule

The prompt context must separate:

- realized income: paid income transactions;
- realized expenses: paid expense transactions;
- pending expenses: pending expense transactions, described as future
  commitments;
- active budgets: all active monthly budgets;
- active goals: only rows from the goals table.

If there are no active goals, the context must state that explicitly. The model
must not infer a financial goal from a budget name.

## Legacy Normalization

Existing rows may contain Markdown fenced JSON. They are recoverable if the
content becomes valid JSON after removing a leading code fence such as
```` ```json ```` and a trailing ```` ``` ````.

Operational normalization for one known row:

1. Read the row by `ai_insights.id`.
2. Strip Markdown fences.
3. Parse JSON.
4. Serialize compact JSON with `ensure_ascii=false`.
5. Update only that row.
6. Re-read and confirm JSON parsing succeeds.

Do not rewrite `llm_audit_logs.response_text`; audit logs must preserve the raw
provider response.
