# workflows

## Objetivo
Definir pipelines de CI/CD e gates de qualidade, seguranca e deploy.

## Workflows principais
- `ci.yml`: lint, type-check, testes, seguranca, quality gate.
- `deploy.yml`: deploy automatizado/controlado por ambiente (DEV/PROD).

## Padroes obrigatorios
- Toda mudanca de workflow deve manter reproducibilidade local quando aplicavel.
- Actions de terceiros devem ser pinadas em versao/commit imutavel.
- Jobs criticos devem expor logs/artifacts suficientes para troubleshooting.

## Governanca
- Checks criticos devem ser required no ruleset do repositorio.
- Falhas de gate bloqueiam merge em branch protegida.
