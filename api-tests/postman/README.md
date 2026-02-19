# postman

## Objetivo
Suite de smoke/regressao REST + GraphQL para validacao rapida de saude funcional da API.

## Arquivos
- `auraxis.postman_collection.json`: colecao principal.
- `environments/local.postman_environment.json`: ambiente local.
- `environments/dev.postman_environment.json`: ambiente DEV.
- `environments/prod.postman_environment.json`: ambiente PROD.

## Convencoes
- Variaveis de ambiente devem manter nomes estaveis (`baseUrl`, `testPassword`, etc.).
- Cenarios de erro GraphQL devem validar codigo publico e nao expor `INTERNAL_ERROR` para erros de credencial invalida.
- Novas requests devem incluir assertions minimas de status e contrato.
