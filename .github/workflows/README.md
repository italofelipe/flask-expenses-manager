# workflows

## Objetivo
Definir pipelines de CI/CD e gates de qualidade, seguranca e deploy.

## Workflows principais
- `ci.yml`: lint, type-check, testes, seguranca, quality gate.
- `deploy.yml`: deploy automatizado/controlado por ambiente (DEV/PROD).
- `governance.yml`: auditoria/sincronizacao do ruleset de branch protection via API do GitHub.
- `aws-security-audit.yml`: auditoria IAM (I8) agendada/manual com artefato JSON.

## Trilha canonica de smoke
- pré-merge: `ci.yml` usa a suite Newman em `scripts/run_postman_suite.sh`
- pós-deploy: `deploy.yml` usa `scripts/http_smoke_check.py`
- nao existe mais workflow paralelo de smoke pos-deploy nem suite legada em `smoke_tests/*`

## Gates oficiais de release (Newman/Postman)
- `CI Runtime Images`: build único das imagens canônicas do CI com artifacts efêmeros para reuso
- `API Release Gate (Postman/Newman Smoke)`: gate rapido obrigatorio de pre-merge para a superficie black-box cross-domain
- `API Release Gate (Postman/Newman Full)`: gate dedicado obrigatorio de integracao/release para a superficie canonica REST + GraphQL nao-privilegiada
- `postman-privileged.yml`: workflow manual separado para fluxos privilegiados/admin; nao participa do caminho comum de merge
- os dois gates oficiais reutilizam a mesma imagem runtime construída no job `CI Runtime Images`
- os dois gates oficiais publicam evidencias separadas como artifacts `newman-smoke-report` e `newman-full-report`

## Sinal de review (Cursor Bugbot)
- O `ci.yml` inclui o job `Review Signal (Cursor Bugbot)` em PR.
- O job executa `scripts/pr_review_signal_check.py` em modo `advisory`.
- Nao e gate obrigatorio no ruleset (evita bloqueio por quota/ruido), mas publica resumo no `Step Summary` para triagem.

## Secrets relevantes
- `TOKEN_GITHUB_ADMIN`: token com permissao de administracao do repositório para auditoria/sync de ruleset no `governance.yml`.

## Observabilidade de CI
- O job `API Release Gate (Postman/Newman Smoke)` aplica `flask db upgrade` antes da suite Postman para evitar falhas de schema em banco efemero.
- O runner Newman do CI e local usa dependencias Node versionadas com `npm ci`, evitando dependencia de install global.
- O job `CI Runtime Images` publica artifacts com `retention-days: 1` para reuso entre smoke/full/security com custo controlado.
- O job `Dependency Security (OSV-Scanner)` publica `osv-results.json` como artifact para auditoria de vulnerabilidades em lockfiles.

## Padroes obrigatorios
- Toda mudanca de workflow deve manter reproducibilidade local quando aplicavel.
- Actions de terceiros devem ser pinadas em versao/commit imutavel.
- Jobs criticos devem expor logs/artifacts suficientes para troubleshooting.

## Governanca
- Checks criticos devem ser required no ruleset do repositorio.
- Falhas de gate bloqueiam merge em branch protegida.
