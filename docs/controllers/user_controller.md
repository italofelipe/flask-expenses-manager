# user_controller.py

Arquivo: `/Users/italochagas/Desktop/projetos/flask/flask-template/app/controllers/user_controller.py`

## Responsabilidade
Gerenciar perfil do usuário autenticado e visão consolidada (`/user/me`) com dados de transações e carteira.

## Blueprint
- Prefixo: `/user`

## Contrato de resposta
- Header opcional: `X-API-Contract: v2`
- Sem header: mantém payload legado atual.
- Com `v2`: retorna envelope padronizado (`success`, `message`, `data`, `error`, `meta`).

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
- Busca transações paginadas do usuário com filtros opcionais (`status`, `month`).
- Busca itens da carteira (`Wallet`) do usuário.
- Retorna um payload consolidado com `user`, `transactions` e `wallet`.

Contrato v2:
- dados em `data.user`, `data.transactions`, `data.wallet`
- paginação em `meta.pagination`

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
1. `/user/me` mistura muitos dados em um endpoint só (payload grande e acoplado).
2. Parse de data manual coexistindo com validação do schema.
3. Respostas e tratamento de erro ainda sem contrato totalmente uniforme com outros módulos.
4. Não há endpoint dedicado para leitura simples de perfil sem transações/carteira.
5. `GET /user/me` mantém acoplamento alto (perfil + transações + carteira em uma rota).

## Recomendação de implementação futura (sem alterar comportamento agora)
- Criar `UserProfileService` e `UserDashboardService` para separar responsabilidades.
- Aplicar DTOs/serializers de resposta com contrato único.
- Cobrir filtros de `/user/me` com testes de integração.
