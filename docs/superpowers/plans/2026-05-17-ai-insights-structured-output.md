# AI Insights Structured Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make AI spending insights persist and return valid structured data that the Web UI can render.

**Architecture:** The API validates LLM output before persistence and returns both `items` and legacy `insights`. The Web app prefers `items` and tolerates legacy fenced JSON. Production repair normalizes only the known malformed `AIInsight` row.

**Tech Stack:** Flask, SQLAlchemy, OpenAI Chat Completions, pytest, Nuxt 4, Vue 3, TypeScript, Vitest.

---

### Task 1: Production Row Normalization

**Files:**
- No repository file changes.
- Production DB row: `ai_insights.id=5508449c-1955-4382-99a7-209092a70d44`

- [x] **Step 1: Read the current content**

Run via AWS SSM on `i-0057e3b52162f78f8`:

```bash
cd /opt/auraxis
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web python - <<'PY'
from uuid import UUID
from app import create_app
from app.extensions.database import db
from app.models.ai_insight import AIInsight

app = create_app(enable_http_runtime=False)
with app.app_context():
    row = db.session.get(AIInsight, UUID("5508449c-1955-4382-99a7-209092a70d44"))
    print(repr(row.content if row else None))
PY
```

- [x] **Step 2: Normalize only that row**

```bash
cd /opt/auraxis
docker compose --env-file .env.prod -f docker-compose.prod.yml exec -T web python - <<'PY'
import json
from uuid import UUID
from app import create_app
from app.extensions.database import db
from app.models.ai_insight import AIInsight

def strip_fence(value: str) -> str:
    text = value.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline != -1:
            text = text[first_newline + 1 :]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()

app = create_app(enable_http_runtime=False)
with app.app_context():
    row = db.session.get(AIInsight, UUID("5508449c-1955-4382-99a7-209092a70d44"))
    parsed = json.loads(strip_fence(row.content))
    row.content = json.dumps(parsed, ensure_ascii=False, separators=(",", ":"))
    db.session.commit()
    print(row.content)
PY
```

- [x] **Step 3: Verify the UI can now parse the cached insight**

Call `GET /ai/insights/spending` with the user token and confirm `data.insights`
starts with `[` and not with a Markdown fence.

Production confirmation via SSM: `updated_id=5508449c-1955-4382-99a7-209092a70d44`,
`after_prefix='[{"type":"pr'`, `items=3`, `valid_json=true`.

### Task 2: Backend Parsing and Structured Output Tests

**Files:**
- Modify: `tests/test_ai_advisory_service.py`
- Modify: `tests/test_ai_insight_persistence.py`
- Modify: `tests/test_ai_insight_goals_budget_context.py`

- [x] **Step 1: Add failing tests**

Add tests asserting that fenced JSON is normalized, `items` is returned,
malformed JSON raises `LLMProviderError`, and pending expenses appear in the
prompt as pending context instead of paid expenses.

- [x] **Step 2: Run focused tests and confirm failure**

```bash
source .venv/bin/activate
python -m pytest \
  tests/test_ai_advisory_service.py \
  tests/test_ai_insight_persistence.py \
  tests/test_ai_insight_goals_budget_context.py \
  -q
```

Expected: new tests fail because the backend currently persists raw LLM text
and has no `items` payload.

Observed RED: `OpenAILLMProvider.generate_with_usage()` rejected
`response_schema`; after provider support, service tests failed on missing
`items`.

### Task 3: Backend Implementation

**Files:**
- Modify: `app/services/llm_provider.py`
- Modify: `app/services/ai_advisory_service.py`
- Modify: `app/controllers/ai/resources.py`
- Modify: `docs/wiki/AI-Insights-Structured-Output.md`

- [x] **Step 1: Add optional response schema support**

Extend the provider protocol to accept `response_schema: dict[str, object] | None`
on `generate_with_usage()`. OpenAI includes `response_format` only when the
schema is provided.

- [x] **Step 2: Add insight item parsing helpers**

Create helpers in `ai_advisory_service.py` to strip fences, parse JSON, validate
`type/title/message`, and serialize canonical JSON.

- [x] **Step 3: Use structured output for spending insights**

Pass the spending insight JSON schema to the provider, validate returned items,
save canonical JSON, and return `items` plus `insights`.

- [x] **Step 4: Enrich prompt context**

Separate paid income, paid expense, pending expense, budgets, and goals. Ensure
the prompt says no active goals exist when that is true.

- [x] **Step 5: Run backend focused tests**

```bash
source .venv/bin/activate
python -m pytest \
  tests/test_ai_advisory_service.py \
  tests/test_ai_insight_persistence.py \
  tests/test_ai_insight_goals_budget_context.py \
  tests/test_ai_daily_rate_limit.py \
  -q
```

Observed GREEN: `102 passed`.

### Task 4: Frontend Contract and Parser

**Files:**
- Modify: `app/features/ai-insights/contracts/ai-insight.ts`
- Modify: `app/features/ai-insights/model/ai-insight.ts`
- Modify: `app/features/ai-insights/model/ai-insight.spec.ts`
- Modify: `app/features/ai-insights/composables/useAIInsights.spec.ts`

- [x] **Step 1: Add failing Vitest coverage**

Add tests for fenced JSON, preferred `items`, legacy JSON, malformed fallback,
and new insight type presentation metadata.

- [x] **Step 2: Implement parser and contract changes**

Add `items?: InsightItem[]` to DTOs, prefer `items` in generated mapping, strip
code fences before parsing strings, and add labels for new types.

- [x] **Step 3: Run frontend focused tests**

```bash
pnpm vitest run app/features/ai-insights/model/ai-insight.spec.ts app/features/ai-insights/composables/useAIInsights.spec.ts
```

Observed GREEN with coverage disabled for focused run:
`pnpm vitest run --coverage.enabled=false ...` -> 2 files, 11 tests passed.

### Task 5: Final Verification and PRs

**Files:**
- API PR closes `italofelipe/auraxis-api#1267`
- Web PR closes `italofelipe/auraxis-web#855`

- [x] **Step 1: API verification**

```bash
bash scripts/run_ci_quality_local.sh --local
```

Observed:

- Focused API regression suite passed:
  `tests/test_llm_provider.py`, `tests/test_ai_advisory_service.py`,
  `tests/test_ai_insight_persistence.py`,
  `tests/test_ai_insight_goals_budget_context.py`,
  `tests/test_ai_daily_rate_limit.py`.
- Focused `ruff check`, focused `mypy`, and `git diff --check` passed.
- Full local gate passed feature flag hygiene, repo hygiene, GraphQL auth config,
  Alembic single-head, entitlement matrix, security exception governance,
  Bandit, `ruff format`, and `ruff check`.
- Full local gate stopped at repository-wide `mypy` baseline with 94 errors in
  34 files outside this change set. No remaining `mypy` errors were reported in
  `app/services/ai_advisory_service.py` or `app/services/llm_provider.py`.

- [x] **Step 2: Web verification**

```bash
pnpm quality-check
```

Observed GREEN: `pnpm quality-check` passed, including lint, typecheck,
coverage (`3266 passed`), policy, contracts, codegen, and production build.

- [ ] **Step 3: Publish draft PRs**

Create one draft PR per repo. Include issue links, production evidence, local
verification, and any known CI caveats.
