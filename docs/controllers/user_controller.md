# user controller

Pacote: `app/controllers/user/`

## Responsabilidade
Gerenciar perfil do usuário autenticado, contrato canônico de contexto (`/user/me`)
e bootstrap agregado explícito (`/user/bootstrap`) para frontend/home.

## Blueprint
- Prefixo: `/user`

## Contrato de resposta
- Header opcional: `X-API-Contract: v2`
- Sem header: mantém payload legado atual.
- Com `v2`: retorna envelope padronizado (`success`, `message`, `data`, `error`, `meta`).
- Com `v3` em `GET /user/me`: retorna apenas o contexto autenticado canônico.

## Helpers internos

## `assign_user_profile_fields(user, data)`
O que faz:
- Mapeia campos permitidos do payload para o model `User`.
- Faz parse manual de datas (`birth_date`, `investment_goal_date`) quando recebidas como string.

## `validate_user_token(user_id, jti)`
O que faz:
- Verifica se usuário existe e se `current_jti` ainda é válido.

## `filter_transactions(user_id, status, month)`
O que faz:
- Cria query base de transações não deletadas.
- Aplica filtro por status.
- Aplica filtro por mês (`YYYY-MM`) usando `extract(year/month)`.

## Recursos e comportamento

## `UserProfileResource.put`
Endpoint: `PUT /user/profile`

O que faz:
- Exige JWT.
- Carrega usuário autenticado.
- Atualiza campos de perfil permitidos.
- Executa validação de negócio via `user.validate_profile_data()`.
- Persiste e retorna snapshot do perfil.

Resposta:
- `200`: perfil atualizado
- `400`: validação inválida
- `401`: token revogado
- `404`: usuário não encontrado
- `500`: erro interno

Contrato v2:
- perfil em `data.user`
- erros com `error.code` (`VALIDATION_ERROR`, `UNAUTHORIZED`, `NOT_FOUND`)

## `UserMeResource.get`
Endpoint: `GET /user/me`

O que faz:
- Exige JWT e valida `jti` atual.
- Com `v3`, retorna apenas contexto autenticado canônico.
- Sem `v3`, preserva o legado:
  - busca transações paginadas com filtros opcionais (`status`, `month`)
  - busca itens da carteira (`Wallet`)
  - retorna payload consolidado com `user`, `transactions` e `wallet`

Contrato v2:
- dados em `data.user`, `data.transactions`, `data.wallet`
- paginação em `meta.pagination`

Contrato v3:
- dados em `data.user.identity`
- dados em `data.user.profile`
- dados em `data.user.financial_profile`
- dados em `data.user.investor_profile`
- dados em `data.user.product_context`
- não aceita semântica de coleção (`page`, `limit`, `status`, `month`)

## `UserBootstrapResource.get`
Endpoint: `GET /user/bootstrap`

O que faz:
- Exige JWT e valida `jti` atual.
- Constrói agregado explícito para home/frontend.
- Reaproveita o mesmo core autenticado de `GET /user/me`.
- Retorna:
  - `user` em shape canônico
  - `transactions_preview` com transações recentes
  - `wallet` com itens e total

Query params:
- `transactions_limit` (default `10`, max `50`)

Critério de uso:
- usar quando web/app precisarem reduzir round-trips na home
- não usar como substituto de `/transactions` e `/wallet` para listagens completas

Query params:
- `page` (default 1)
- `limit` (default 10)
- `status`
- `month` (`YYYY-MM`)

## Dependências principais
- `app.models.user.User`
- `app.models.transaction.Transaction`
- `app.models.wallet.Wallet`
- `UserProfileSchema`
- `PaginatedResponse`

## Pontos incompletos / melhorias (Fase 0)
1. o legado de `/user/me` continua carregando acoplamento alto até os consumidores migrarem.
2. Parse de data manual coexistindo com validação do schema.
3. Respostas e tratamento de erro ainda sem contrato totalmente uniforme com outros módulos.
4. a migração dos consumidores para `/user/me` `v3` e `/user/bootstrap` ainda precisa ser concluída.
5. o bootstrap continua agregado por desenho e deve permanecer leve para não virar nova coleção canônica.

## Recomendação de implementação futura (sem alterar comportamento agora)
- concluir a migração dos clientes para o contrato canônico de `/user/me`;
- manter `/user/bootstrap` apenas como agregado leve de tela;
- evitar reintroduzir filtros/coleções completas no bootstrap.
