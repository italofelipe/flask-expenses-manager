# postman

## Objetivo
Suite canonica black-box da API Auraxis para importacao direta no Postman e execucao automatizada com Newman.

Ela cobre as superficies REST criticas por dominio e um smoke representativo de GraphQL. A colecao oficial fica em:
- `api-tests/postman/auraxis.postman_collection.json`

## Estrutura oficial
- `00 - Health`
- `01 - Auth`
- `02 - User`
- `03 - Transactions`
- `04 - Budgets`
- `05 - Goals`
- `06 - Wallet`
- `07 - Simulations`
- `08 - Entitlements`
- `09 - Notifications`
- `10 - LGPD`
- `11 - AI Advisory`
- `99 - Cleanup`

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
  - `full`: roda a colecao completa nao-privilegiada;
  - `privileged`: roda o subconjunto com bootstrap minimo + fluxos admin/privilegiados;
  - `smoke`: roda o subconjunto canônico mínimo por dominio.

## Fonte de dados

A collection e gerada automaticamente a partir do `openapi.json` (raiz do repo) pelo script `scripts/openapi_to_postman.py`. O OpenAPI e a fonte unica de verdade.

Fluxo de atualizacao:
1. Altere controllers/schemas no Flask
2. Regere o spec: `flask openapi-export --output openapi.json`
3. Regere a collection: `npm run postman:build`
4. Commite ambos (`openapi.json` + `auraxis.postman_collection.json`)

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
npm run postman:privileged:dev
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
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile privileged
```

Rodar fluxos privilegiados:
```bash
POSTMAN_ENABLE_PRIVILEGED_FLOWS=true \
POSTMAN_ADMIN_TOKEN=<token-admin> \
./scripts/run_postman_suite.sh ./api-tests/postman/environments/dev.postman_environment.json --profile privileged
```

## Integracao CI
- `smoke` e o gate oficial rapido de release/pre-merge para saude funcional cross-domain.
- `full` e o gate oficial dedicado de release/integracao para a superficie canonica nao-privilegiada.
- merge/release readiness exige `smoke` + `full` verdes; `privileged` continua fora do caminho comum.
- `privileged` fica em workflow manual separado, porque exige `adminToken` explicito.
- Todos usam a mesma collection canonica; muda apenas o `suiteProfile`.
