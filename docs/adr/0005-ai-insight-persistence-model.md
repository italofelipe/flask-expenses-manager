# ADR 0005 — Modelo de Persistência de AI Insights

**Status:** Accepted
**Data:** 2026-05-12
**Issues:** #1227, #1228

---

## Contexto

Antes deste ADR, os insights gerados pelo `AIAdvisoryService` eram apenas logados em `llm_audit_logs` (tabela de auditoria de custo/tokens). Isso significava que:
- Insights não eram recuperáveis por data
- Não havia histórico para o usuário
- O AI não tinha acesso ao insight anterior para injetar contexto

Precisávamos decidir: usar `llm_audit_logs` como store primário ou criar uma nova tabela `ai_insights`.

---

## Decisão

**Criar uma tabela separada `ai_insights` como store primário.**

`llm_audit_logs` continua existindo como registro financeiro/de auditoria (custo, tokens, latência por chamada). É write-only da perspectiva da aplicação.

`ai_insights` é o registro de produto — recuperável, exibível ao usuário, encadeável via `previous_insight_id`.

---

## Motivação

### Por que não usar `llm_audit_logs` como store primário?

1. **Separação de responsabilidades:** `llm_audit_logs` é auditoria técnica (custo, latência, prompt raw). `ai_insights` é produto (o que o usuário vê, o que o AI lê como contexto).

2. **Schema diferente:** O audit log armazena o prompt completo (dados potencialmente sensíveis). O insight armazena apenas o `content` (resultado final) — menor superfície de exposição.

3. **Endpoint de histórico:** `GET /ai/insights/history` precisaria de joins e filtros complexos sobre `llm_audit_logs` para distinguir "insight diário manual" de "job semanal batch" de "chamada interna". Com `ai_insights`, o filtro é simples: `WHERE user_id = ? ORDER BY created_at DESC`.

4. **Context injection:** O AI precisa ler o insight anterior (`previous_insight_id`). Em `llm_audit_logs` isso seria buscar o `response_text` mais recente de endpoint `spending_insights` — frágil e lento.

---

## Estrutura decidida

### ai_insights
- Campos de produto: `content`, `insight_type`, `period_label`, `period_start`, `period_end`
- Metadados técnicos mínimos: `model`, `tokens_used`, `cost_usd`
- Self-referential FK: `previous_insight_id` → cadeia de contexto entre dias

### llm_audit_logs (inalterado)
- Continua recebendo TODA chamada LLM (via `_log_llm_call()`)
- Inclui `prompt` completo, `response_text` completo, latência
- Serve para auditoria de custo e debugging

---

## Convenção de enums

`insight_type` usa `native_enum=False` (VARCHAR + CHECK constraint) em vez de `CREATE TYPE` PostgreSQL.

**Motivo:** Em conformidade com a resolução pós-post-mortem PR #1174. `native_enum=True` (default SQLAlchemy) registra DDL listener que emite `CREATE TYPE` antes da migration, causando conflito quando a migration tenta criá-lo novamente → falha silenciosa no CI.

---

## Idempotência por `period_label`

O campo `period_label` é a chave natural de idempotência:

| Tipo | Formato | Exemplo |
|------|---------|---------|
| daily | `YYYY-MM-DD` | `2026-05-12` |
| weekly | `YYYY-WNN` | `2026-W20` |
| monthly | `YYYY-MM` | `2026-05` |
| recap | `YYYY-MM-recap` | `2026-05-recap` |

A query `_get_cached_insight(user_id, insight_type, period_label)` garante que uma segunda chamada no mesmo dia retorna o insight existente sem chamar o LLM.

---

## Consequências

**Positivas:**
- Histórico completo disponível via `GET /ai/insights/history`
- Context injection simples via `_get_latest_insight(user_id)`
- Schema limpo e orientado ao produto
- `llm_audit_logs` permanece como fonte de verdade de custo

**Negativas/Trade-offs:**
- Dois stores para a mesma chamada LLM (overhead de escrita)
- `cost_usd` e `tokens_used` ficam denormalizados em dois lugares
- Eventual inconsistência se `_save_insight` falhar após `_log_llm_call` (mitigado: falha no audit log é silenciosa e não impede o insight de ser retornado)
