# scripts

## Objetivo
Scripts operacionais e de engenharia para CI/CD, seguranca, deploy, observabilidade e validacoes locais.

## Tipos de script
- CI/qualidade: checks locais e gates de pipeline.
- Seguranca: evidencias, hardening, auditoria e enforce.
- AWS/operacao: deploy via SSM, backups, patching, monitoramento.
- Testes de API: execucao de suites Postman/Newman.

## Padroes obrigatorios
- Scripts devem ser idempotentes sempre que possivel.
- Falhas precisam ser explicitas, com mensagens acionaveis.
- Evitar side-effects silenciosos.
- Parametros sensiveis devem vir por env vars, nunca hardcoded.

## Uso recomendado
- Antes de push: rodar `scripts/run_ci_like_actions_local.sh`.
- Para smoke API: `scripts/run_postman_suite.sh`.
