# postman

## Objetivo
Suite canonica black-box da API Auraxis para importacao direta no Postman e execucao automatizada com Newman.

Ela cobre as superficies REST criticas por dominio e um smoke representativo de GraphQL. A colecao oficial fica em:
- `api-tests/postman/auraxis.postman_collection.json`

## Estrutura oficial
- `00 - Auth and User Bootstrap`
- `01 - Transactions`
- `02 - Goals`
- `03 - Wallet`
- `04 - Simulations`
- `05 - GraphQL`

## Ambientes versionados
- `environments/local.postman_environment.json`
- `environments/dev.postman_environment.json`
- `environments/prod.postman_environment.json`

Os environments devem conter apenas valores seguros para versionamento:
- `baseUrl`
- `testPassword`
- `testPasswordWrong`
- `enablePrivilegedFlows`
- `adminToken`

## Regras operacionais
- Existe uma unica collection canonica. Nao manter exports duplicados, mocks soltos ou snapshots antigos fora desta arvore.
- Requests devem usar assertions minimas de status + contrato.
- IDs e tokens devem ser encadeados por collection variables.
- Fluxos privilegiados devem ser opcionais e gateados por `enablePrivilegedFlows=true` e `adminToken`.
- O subset padrao que roda no CI deve continuar deterministico e seguro sem token administrativo.
- `suiteProfile` governa o recorte oficial da execução:
  - `full`: roda a colecao completa;
  - `smoke`: roda o subconjunto canônico mínimo por dominio.

## Execucao
Gerar/regravar a collection oficial:
```bash
npm run postman:build
```

Rodar localmente com Newman:
```bash
npm ci
npm run postman:local
```

Perfis oficiais:
```bash
npm run postman:smoke:local
npm run postman:full:local
```

Perfis oficiais do CI:
```bash
npm run postman:smoke:ci
npm run postman:full:ci
```

Rodar com outro environment:
```bash
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json
./scripts/run_postman_suite.sh ./api-tests/postman/environments/prod.postman_environment.json
```

Rodar com perfil explícito:
```bash
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile smoke
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile full
```

Rodar fluxos privilegiados:
```bash
POSTMAN_ENABLE_PRIVILEGED_FLOWS=true \
POSTMAN_ADMIN_TOKEN=<token-admin> \
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json
```

## Integracao CI
- `smoke` continua sendo o gate rapido minimo para saude funcional cross-domain.
- `full` roda em job dedicado de integracao, com report JUnit separado.
- Ambos usam a mesma collection canonica; muda apenas o `suiteProfile`.
