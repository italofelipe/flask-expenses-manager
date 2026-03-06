# scripts

## Objetivo
Scripts operacionais e de engenharia para CI/CD, seguranca, deploy, observabilidade e validacoes locais.

## Tipos de script
- CI/qualidade: checks locais e gates de pipeline.
- Seguranca: evidencias, hardening, auditoria e enforce.
- AWS/operacao: deploy via SSM, backups, patching, monitoramento.
- Testes de API: execucao de suites Postman/Newman.
- Governanca GitHub: auditoria/sincronizacao de ruleset de branch protegida.

## Padroes obrigatorios
- Scripts devem ser idempotentes sempre que possivel.
- Falhas precisam ser explicitas, com mensagens acionaveis.
- Evitar side-effects silenciosos.
- Parametros sensiveis devem vir por env vars, nunca hardcoded.

## Uso recomendado
- Bootstrap local portável: `bash scripts/bootstrap_local_env.sh`.
- Executar módulo Python com o interpreter da repo: `scripts/python_tool.sh <module> [args...]`.
- Executar script Python com o interpreter da repo: `scripts/python_exec.sh <script.py> [args...]`.
- Executar binário da `.venv` com fallback seguro: `scripts/repo_bin.sh <tool> [args...]`.
- Antes de push: rodar `scripts/run_ci_like_actions_local.sh`.
- Para smoke API: `scripts/run_postman_suite.sh`.
- Para smoke HTTP pós-deploy (REST + GraphQL): `scripts/python_exec.sh scripts/http_smoke_check.py --base-url <url> --env-name <dev|prod>`.
- Para contrato OpenAPI determinístico: `bash scripts/run_schemathesis_contract.sh`.
- Para sinal de review Cursor Bugbot: `scripts/python_exec.sh scripts/pr_review_signal_check.py --repo <owner/repo> --pr-number <numero> --mode advisory`.
- Para governanca de branch: `scripts/python_exec.sh scripts/github_ruleset_manager.py --owner <owner> --repo <repo> --mode audit`.
- Para auditoria IAM contínua: `scripts/python_exec.sh scripts/aws_iam_audit_i8.py --profile auraxis-admin --region us-east-1 --fail-on fail --output-json reports/aws-iam-audit.json`.
- Secret esperado no GitHub Actions para governanca: `TOKEN_GITHUB_ADMIN`.
