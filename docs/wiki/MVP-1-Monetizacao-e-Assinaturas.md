# Monetização e Assinaturas — MVP1

> **Fonte canônica de preços:** `app/config/billing_plans.py`
> Decisão registrada em DEC-168 (2026-04-05, founder-confirmed).

## Planos

| Plano | Preço | Ciclo | Trial | Destacado |
|-------|-------|-------|-------|-----------|
| Free | R$0,00 | — | — | — |
| Premium Mensal | R$27,90 | Mensal | 7 dias | ✓ |
| Premium Anual | R$220,00 | Anual | 7 dias | — |

**Equivalência anual:** R$220,00/ano = R$18,33/mês (34% de desconto vs mensal).

## Features por plano

| Feature | Free | Premium |
|---------|------|---------|
| Transações (CRUD) | ✓ | ✓ |
| Metas financeiras | limitado | ✓ |
| Análises com IA | — | ✓ |
| Alertas de vencimento | — | ✓ |
| Briefing semanal | — | ✓ |
| Export PDF/CSV | — | ✓ |
| Suporte prioritário | — | ✓ |

## PSP / Gateway

- Provedor: **Asaas**
- Adapter: `app/services/billing/asaas_billing_adapter.py`
- Stub para dev/test: `app/services/billing/stub_billing_adapter.py`
- Webhook: `POST /billing/webhook`

## Endpoints de billing

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/billing/plans` | Lista planos públicos |
| POST | `/billing/subscribe` | Inicia assinatura |
| POST | `/billing/cancel` | Cancela assinatura |
| GET | `/billing/status` | Status da assinatura do usuário |
| POST | `/billing/webhook` | Webhook de eventos do PSP |

## Decisões

- **DEC-168 (2026-04-05):** Preço de lançamento definido como R$27,90/mês (founder-confirmed).
  Revisão de preço prevista pós-product-market-fit.
- Plano Free sem checkout — `checkout_enabled=False`.
- Trial de 7 dias para planos Premium (mensal e anual).
