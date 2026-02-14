# Cloud Deploy Analysis (AWS vs Azure)

Atualizado em: 2026-02-14
Objetivo: preparar deploy e operacao com orçamento de ate **R$70/mês**.

## Premissas
- Budget alvo: `R$70/mês`.
- Conversão conservadora usada para análise: `US$1 ~= R$6,00`.
- Carga inicial baixa (POC/MVP), sem alta disponibilidade.
- Aplicação em Docker.

## Viabilidade rápida
- Mesmo com orçamento de R$70 (~US$11,67), banco gerenciado dedicado (RDS/Azure PostgreSQL) tende a consumir a maior parte do budget e pode estourar o teto (dependendo de FX e storage/backups).
- Estratégia mais viável no curto prazo: app + PostgreSQL no mesmo host (self-managed) com Docker.

## AWS (estimativa)
- Lightsail Linux/Unix (faixa inicial citada na página oficial): `US$5/mês`.
- RDS PostgreSQL `db.t4g.micro` Single-AZ (us-east-1): `US$0.016/h` (~`US$11.68/mês` em 730h).
- RDS GP3 storage: `US$0.115/GB-mês` (ex.: 20 GB ~= `US$2.30/mês`).

Conclusão AWS:
- Plano enxuto com host único: viável perto do budget.
- Plano com RDS dedicado: geralmente não viável com o budget atual, a menos que haja aumento de orçamento ou ajuste de escopo.

## Azure (estimativa)
- VM `Standard_B1s` Linux (eastus): `US$0.0104/h` (~`US$7.59/mês` em 730h), sem disco/tráfego.
- Azure Database for PostgreSQL Flexible Server (tier básico encontrado): `US$0.017/h` (~`US$12.41/mês` em 730h), sem storage.
- Storage PostgreSQL: ordem de grandeza `US$0.115/GB-mês` em itens de preço da API.

Conclusão Azure:
- Mesmo cenário mínimo tende a superar US$6,67/mês.
- Com DB gerenciado + VM, custo fica significativamente acima do budget.

## Decisão recomendada (MVP)
- Provedor recomendado: **AWS**.
- Motivo: melhor chance de caber no orçamento mensal de R$40 com setup mínimo.
  - Observacao: agora o budget alvo e R$70/mes, mas a estrategia continua a mesma (host unico + DB self-managed).

## Plano A (recomendado para budget)
- Infra: 1 instância (Lightsail/EC2 low-cost).
- Stack em Docker Compose no host:
  - `web` (Flask + gunicorn)
  - `postgres` (container)
  - `reverse proxy` opcional (Nginx/Caddy)
- Backup:
  - dump diário do Postgres para bucket/objeto
  - retenção curta (ex.: 7-14 dias)

Riscos:
- sem alta disponibilidade;
- responsabilidade operacional maior (DB self-managed);
- maior cuidado com backup/restore.

## Plano B (fallback se Plano A falhar)
- Migrar DB para gerenciado (RDS PostgreSQL) e manter app em host único.
- Ganho: melhor operação de banco (backup/restore gerenciado).
- Perda: custo mensal sobe e tende a estourar o budget atual.

Critério de troca A -> B:
- falhas recorrentes de integridade/restore no banco self-managed;
- necessidade de RPO/RTO mais agressivo;
- aumento de orçamento mensal.

## Guardrails de custo (recomendado)
- Configurar AWS Budgets + Cost Anomaly Detection com limite conservador em USD.
- Documento: `docs/AWS_COST_GUARDRAILS.md`

## PostgreSQL local (máquina do desenvolvedor) vs cloud
- Não recomendado para produção usar banco na máquina local do dev.
- Problemas:
  - indisponibilidade quando máquina está offline;
  - segurança/rede complexa (exposição de porta, VPN, IP dinâmico);
  - baixa confiabilidade para backup/monitoramento.
- Para produção, preferir:
  - PostgreSQL no host cloud (Plano A), ou
  - RDS (Plano B, se orçamento permitir).

## Fontes
- AWS Lightsail Pricing:
  - https://aws.amazon.com/lightsail/pricing/
- AWS RDS price list (us-east-1, PostgreSQL):
  - https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonRDS/current/us-east-1/index.json
- Azure Retail Prices API (VM B1s, eastus):
  - https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&$filter=serviceName%20eq%20%27Virtual%20Machines%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20armSkuName%20eq%20%27Standard_B1s%27%20and%20priceType%20eq%20%27Consumption%27
- Azure Retail Prices API (Azure Database for PostgreSQL, eastus):
  - https://prices.azure.com/api/retail/prices?api-version=2023-01-01-preview&$filter=serviceName%20eq%20%27Azure%20Database%20for%20PostgreSQL%27%20and%20armRegionName%20eq%20%27eastus%27%20and%20priceType%20eq%20%27Consumption%27
