# Plano B: RDS PostgreSQL (somente se budget permitir)

Contexto:
- O projeto tem teto de custo mensal (objetivo atual): **R$70/mes**.
- RDS tende a **consumir a maior parte do budget** mesmo no menor tamanho util.

## Status atual
- **Nao provisionado**.
- Plano A (atual): PostgreSQL em container na propria VM + backups para S3 + restore drill.

## Por que nao provisionamos agora
- Mesmo instancias pequenas (ex.: `db.t4g.micro`) + storage + backups costumam ultrapassar o budget alvo com folga, dependendo de FX e uso.

## Quando migrar A -> B (criterios objetivos)
- Incidentes recorrentes de banco (corrompimento, falta de espaco, instabilidade) que nao sao resolvidos com hardening/rotina de backup.
- Necessidade de RPO/RTO melhor do que o setup atual consegue entregar.
- Aumento do budget mensal (aceite explicito).

## Como migrar (alto nivel)
1) Criar RDS (Single-AZ) com tamanho minimo viavel e storage baixo (ex.: 20GB).
2) Restaurar um dump recente do S3 no RDS.
3) Ajustar `.env.prod` para usar `DATABASE_URL` apontando para o endpoint do RDS.
4) Rodar migrations.
5) Validar `/healthz` e rotas criticas.
6) Habilitar backups gerenciados do RDS e revisar retention.

## Riscos
- Custo mensal aumenta e pode sair do teto.
- Mudanca de topologia exige revisao de security groups e hardening adicional.

