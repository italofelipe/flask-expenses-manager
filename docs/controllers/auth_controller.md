# auth_controller.py

Arquivo: `/Users/italochagas/Desktop/projetos/flask/flask-template/app/controllers/auth_controller.py`

## Responsabilidade
Gerenciar autenticação e sessão JWT:
- registro de usuário
- login
- logout
- tratamento global de erro de validação do Webargs

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

Resposta:
- `201`: usuário criado
- `409`: email já registrado
- `500`: erro ao persistir

## `AuthResource.post`
Endpoint: `POST /auth/login`

O que faz:
- Aceita login por `email` ou `name` + `password`.
- Verifica senha com `check_password_hash`.
- Cria JWT com expiração de 1 hora.
- Atualiza `current_jti` do usuário para invalidar sessões antigas.

Resposta:
- `200`: token + dados do usuário
- `400`: credenciais ausentes
- `401`: credenciais inválidas
- `500`: erro interno

## `LogoutResource.post`
Endpoint: `POST /auth/logout`

O que faz:
- Exige JWT válido.
- Obtém usuário autenticado.
- Zera `current_jti` para revogar token atual.

Resposta:
- `200`: logout realizado

## `handle_webargs_error`
Escopo global para erros de validação Webargs/Marshmallow.

O que faz:
- Converte erros de validação para HTTP `400` com payload JSON.
- Possui mensagem customizada para falha no campo `password`.

## Dependências principais
- `app.models.user.User`
- `UserRegistrationSchema`, `AuthSchema`
- `flask_jwt_extended`
- `app.extensions.database.db`

## Pontos incompletos / melhorias (Fase 0)
1. Contrato de resposta ainda não está 100% padronizado com os demais controllers.
2. Não há refresh token (somente access token curto).
3. Mensagens estão mistas em português/inglês.
4. Não há limitação explícita de tentativas de login (rate limit / anti brute-force).

## Recomendação de implementação futura (sem alterar comportamento agora)
- Extrair regras de autenticação para serviço dedicado (`AuthService`).
- Centralizar resposta de erro/sucesso em um response builder.
- Adicionar testes de fluxo completo (register/login/logout/token revogado).
