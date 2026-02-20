# workflows

## Objetivo
Definir pipelines de CI/CD e gates de qualidade, seguranca e deploy.

## Workflows principais
- `ci.yml`: lint, type-check, testes, seguranca, quality gate.
- `deploy.yml`: deploy automatizado/controlado por ambiente (DEV/PROD).
- `governance.yml`: auditoria/sincronizacao do ruleset de branch protection via API do GitHub.
- `aws-security-audit.yml`: auditoria IAM (I8) agendada/manual com artefato JSON.

## Sinal de review (Cursor Bugbot)
- O `ci.yml` inclui o job `Review Signal (Cursor Bugbot)` em PR.
- O job executa `scripts/pr_review_signal_check.py` em modo `advisory`.
- Nao e gate obrigatorio no ruleset (evita bloqueio por quota/ruido), mas publica resumo no `Step Summary` para triagem.

## Secrets relevantes
- `TOKEN_GITHUB_ADMIN`: token com permissao de administracao do repositório para auditoria/sync de ruleset no `governance.yml`.

## Observabilidade de CI
- O job `API Smoke (Postman/Newman)` aplica `flask db upgrade` antes da suite Postman para evitar falhas de schema em banco efemero.

## Padroes obrigatorios
- Toda mudanca de workflow deve manter reproducibilidade local quando aplicavel.
- Actions de terceiros devem ser pinadas em versao/commit imutavel.
- Jobs criticos devem expor logs/artifacts suficientes para troubleshooting.

## Governanca
- Checks criticos devem ser required no ruleset do repositorio.
- Falhas de gate bloqueiam merge em branch protegida.
