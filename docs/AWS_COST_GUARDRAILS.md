# AWS Cost Guardrails (Budget <= R$70/mes)

Objetivo: manter o custo mensal do projeto dentro do teto de **R$70/mes**.

Limites:
- AWS nao oferece "hard cap" perfeito para contas comuns. O mecanismo mais proximo e **AWS Budgets** (alertas) + **Cost Anomaly Detection** (anomalias).
- Esses mecanismos **alertam**, mas nao impedem 100% o gasto. Para "cap" real, seria necessario automacao de corte (por exemplo: parar instancias ao ultrapassar limite), o que causa downtime.

## Decisao
- Usar um limite conservador em USD no AWS Budgets:
  - Default do projeto: **USD 10**/mes.
- Alertas:
  - ACTUAL >= 80% do budget (aviso cedo)
  - FORECASTED >= 100% do budget (se previsao estourar)
- Anomalias:
  - Subscription diaria por EMAIL (limitacao da API do Cost Explorer).

## Aplicar/atualizar guardrails (CLI)

```bash
./.venv/bin/python scripts/aws_cost_guardrails_i5.py \
  --profile auraxis-admin \
  --region us-east-1 \
  --usd-limit 10 \
  --email felipe.italo@hotmail.com \
  --enable-anomaly-detection
```

## Onde isso aparece no console AWS
- Billing and Cost Management
  - Budgets
  - Cost Anomaly Detection

## Checklist mensal (operacional)
1) Verificar se o budget esta ativo e o limite ainda faz sentido para o cambio do momento.
2) Verificar se existem alertas/anomalias recentes.
3) Se o custo estiver subindo:
   - revisar instancias/volumes/snapshots;
   - reduzir retention de logs/backups;
   - considerar desligar DEV fora do horario de uso.

