# api-tests

## Objetivo
Centraliza suites de testes de API orientadas a contrato e regressao funcional (consumiveis por ferramentas externas como Postman/API Dog/Newman).

## Estrutura
- `postman/`: colecao principal de smoke/regressao e environments por ambiente.

## Padroes obrigatorios
- Suites devem ser idempotentes e independentes entre execucoes.
- Testes precisam validar status HTTP e contrato sem depender de ordem global.
- Cenarios sensiveis (auth/erro) devem checar ausencia de vazamento interno.

## Execucao
- Runner recomendado: `scripts/run_postman_suite.sh`.
- CI executa smoke com stack local via Docker Compose.
