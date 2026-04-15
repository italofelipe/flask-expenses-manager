# 05 — Auth Flow

Fluxo completo de autenticação: registro, login, refresh token rotation, multi-device sessions e revogação.

## Login e emissão de tokens

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant C as Client (web/app)
    participant N as Nginx
    participant A as auraxis-api
    participant G as Login Guard (Redis)
    participant DB as PostgreSQL
    participant R as Redis

    U->>C: Informa e-mail + senha
    C->>N: POST /auth/login
    N->>A: proxy

    A->>G: Verifica tentativas por e-mail/IP
    alt Limite excedido
        G-->>A: bloqueado (rate limit)
        A-->>C: 429 Too Many Requests
    end

    A->>DB: Busca usuário por e-mail
    A->>A: bcrypt.verify(password, hash)
    alt Senha inválida
        A->>G: Incrementa contador
        A-->>C: 401 Unauthorized
    end

    A->>A: Gera access JWT (15min) + refresh JWT (30d)\nambos com JTI únicos
    A->>DB: INSERT RefreshToken(jti, access_jti, family_id, user_agent, remote_addr)
    A->>R: SET session:{user_id}:{jti} (TTL 30d)
    A->>G: Reset contador
    A-->>C: 200 { token, refresh_token }
    C->>C: Armazena tokens (memória / secure storage)
```

## Refresh Token Rotation

```mermaid
sequenceDiagram
    autonumber
    actor C as Client
    participant A as auraxis-api
    participant DB as PostgreSQL

    C->>A: POST /auth/refresh  {refresh_token}

    A->>A: Decodifica JWT, extrai refresh_jti
    A->>DB: SELECT RefreshToken WHERE jti = refresh_jti

    alt Token não encontrado
        A-->>C: 401 Unauthorized
    end

    alt Token revogado (reuse detection)
        A->>DB: Revoga TODA a família (family_id)
        A-->>C: 401 TokenReuseError — sessão comprometida
    end

    A->>A: Gera novos access JWT + refresh JWT
    A->>DB: UPDATE antigo → revoked_at = now()\nINSERT novo RefreshToken (mesma family_id)
    A-->>C: 200 { token, refresh_token }
```

## Multi-Device Sessions

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuário
    participant C as Client
    participant A as auraxis-api
    participant DB as PostgreSQL

    Note over U,DB: Cada dispositivo tem sua própria linha em RefreshToken

    U->>C: GET /auth/sessions
    C->>A: GET /auth/sessions  (Bearer access_token)
    A->>A: Extrai user_id do JWT
    A->>DB: SELECT RefreshToken WHERE user_id = ? AND revoked_at IS NULL
    A->>A: Marca is_current = (current_access_jti == access_jti do token)
    A-->>C: 200 { sessions: [{id, device_info, created_at, expires_at, is_current}] }

    U->>C: Revoga sessão específica
    C->>A: DELETE /auth/sessions/{session_id}
    A->>DB: UPDATE RefreshToken SET revoked_at = now()\nWHERE id = ? AND user_id = ?
    A-->>C: 200 { revoked: 1 }

    U->>C: Logout global (revogar tudo)
    C->>A: DELETE /auth/sessions
    A->>DB: UPDATE RefreshToken SET revoked_at = now()\nWHERE user_id = ? AND revoked_at IS NULL
    A-->>C: 200 { revoked: N }
    Note over C: Access token atual também invalida\npor ausência de JTI ativo
```

## Validação de Access Token em cada request

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant A as auraxis-api (middleware)
    participant DB as PostgreSQL

    C->>A: GET /any-protected-endpoint  Authorization: Bearer {access_token}
    A->>A: Decodifica JWT (verifica assinatura + exp)
    alt JWT expirado ou inválido
        A-->>C: 401 Unauthorized
    end
    A->>A: Extrai access_jti do payload
    A->>DB: SELECT EXISTS(\n  RefreshToken WHERE current_access_jti = access_jti\n  AND revoked_at IS NULL AND user_id = ?\n)
    alt JTI não encontrado (sessão revogada)
        A-->>C: 401 Unauthorized
    end
    A->>A: Injeta current_user no request context
    A-->>C: Processa request normalmente
```
