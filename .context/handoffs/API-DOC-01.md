# API-DOC-01

## O que foi feito
- Fundação do export estático da documentação GraphQL.
- Catálogo tipado de operações com domínio, acesso e entitlement.
- Exportador versionável para `schema.graphql`, `graphql.introspection.json` e `graphql.operations.manifest.json`.
- Alinhamento dos `.env.example` com os defaults reais de autorização pública GraphQL.

## O que foi validado
- Paridade entre catálogo e root fields do runtime Graphene.
- Paridade entre artefatos commitados e bundle gerado pelo runtime.
- Cobertura explícita das operações premium do `J15`.

## Riscos pendentes
- O portal público ainda depende dos blocos da `platform` para consumir esses artefatos.
- Se novas operações GraphQL forem criadas sem atualizar o catálogo, os testes de paridade devem quebrar no CI.

## Próximo passo
- Executar `[PLT] DOC-03` para publicar `docs.auraxis.com.br/graphql/` usando os artefatos offline gerados aqui.
