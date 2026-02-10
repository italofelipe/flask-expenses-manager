# auth_controller.py

Arquivo: `/opt/auraxis/app/controllers/auth_controller.py`

## Responsabilidade
Gerenciar autenticação e sessão JWT:
- registro de usuário
- login
- logout
- tratamento global de erro de validação do Webargs
- compatibilidade de contrato de resposta (`legacy` e `v2`)

## Blueprint
- Prefixo: `/auth`

## Recursos e comportamento

## `RegisterResource.post`
Endpoint: `POST /auth/register`

O que faz:
- Valida payload com `UserRegistrationSchema`.
- Verifica unicidade de email.
- Gera hash da senha com `generate_password_hash`.
- Persiste usuário e retorna dados públicos.
- Aceita header opcional `X-API-Contract: v2` para envelope padronizado.

Resposta:
- `201`: usuário criado
- `409`: email já registrado
- `500`: erro ao persistir

Contrato:
- Sem header: legado (`message`, `data`).
- Com `X-API-Contract: v2`: `success`, `message`, `data.user`.

## `AuthResource.post`
Endpoint: `POST /auth/login`

O que faz:
- Aceita login por `email` ou `name` + `password`.
- Verifica senha com `check_password_hash`.
- Cria JWT com expiração de 1 hora.
- Atualiza `current_jti` do usuário para invalidar sessões antigas.
- Aceita header opcional `X-API-Contract: v2` para envelope padronizado.

Resposta:
- `200`: token + dados do usuário
- `400`: credenciais ausentes
- `401`: credenciais inválidas
- `500`: erro interno

Contrato:
- Sem header: legado (`message`, `token`, `user`).
- Com `X-API-Contract: v2`: `success`, `message`, `data.token`, `data.user`.

## `LogoutResource.post`
Endpoint: `POST /auth/logout`

O que faz:
- Exige JWT válido.
- Obtém usuário autenticado.
- Zera `current_jti` para revogar token atual.
- Aceita header opcional `X-API-Contract: v2` para envelope padronizado.

Resposta:
- `200`: logout realizado

Contrato:
- Sem header: legado (`message`).
- Com `X-API-Contract: v2`: `success`, `message`, `data`.

## `handle_webargs_error`
Escopo global para erros de validação Webargs/Marshmallow.

O que faz:
- Converte erros de validação para HTTP `400` com payload JSON.
- Possui mensagem customizada para falha no campo `password`.
- Com `X-API-Contract: v2`, retorna erro padronizado com `error.code=VALIDATION_ERROR`.

## Dependências principais
- `app.models.user.User`
- `UserRegistrationSchema`, `AuthSchema`
- `flask_jwt_extended`
- `app.extensions.database.db`

## Pontos incompletos / melhorias (Fase 0)
1. Não há refresh token (somente access token curto).
2. Mensagens estão mistas em português/inglês.
3. Não há limitação explícita de tentativas de login (rate limit / anti brute-force).
4. Não há auditoria de tentativas de autenticação (sucesso/falha) para observabilidade.

## Recomendação de implementação futura (sem alterar comportamento agora)
- Extrair regras de autenticação para serviço dedicado (`AuthService`).
- Centralizar resposta de erro/sucesso em um response builder.
- Adicionar testes de fluxo completo (register/login/logout/token revogado).
