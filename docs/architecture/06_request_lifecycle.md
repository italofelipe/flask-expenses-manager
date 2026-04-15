# 06 — Request Lifecycle

Ciclo de vida completo de uma requisição REST autenticada, do cliente ao banco de dados.

## REST — request autenticado (ex: POST /transactions)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant NG as Nginx
    participant GN as Gunicorn (WSGI)
    participant FL as Flask App
    participant MW as JWT Middleware
    participant BL as Blueprint\n(transaction)
    participant CT as Controller\n(contracts + validation)
    participant SV as Service\n(transaction_service)
    participant DB as PostgreSQL
    participant RD as Redis
    participant R as Response Contract

    C->>NG: POST /transactions  {body}  Bearer token
    NG->>GN: Proxy (HTTP/1.1, timeout 60s)
    GN->>FL: WSGI environ

    FL->>MW: before_request hooks
    MW->>MW: Decodifica JWT, verifica assinatura
    MW->>DB: SELECT RefreshToken WHERE current_access_jti = ? AND revoked_at IS NULL
    alt Inválido/revogado
        MW-->>C: 401
    end
    MW->>FL: g.current_user = User(...)

    FL->>BL: Route dispatch → blueprint handler
    BL->>CT: Instancia RequestSchema (Marshmallow)
    CT->>CT: schema.load(request.json) — valida campos, tipos, regras
    alt Validation error
        CT-->>C: 400 { errors: {...} }
    end

    CT->>SV: create_transaction(user_id, validated_data)
    SV->>SV: Aplica regras de negócio\n(categoria, recorrência, limites)
    SV->>DB: INSERT transaction (SQLAlchemy)
    SV->>DB: UPDATE budget totals (se aplicável)
    SV->>RD: Invalidate cache keys (user:{id}:dashboard:*)
    DB-->>SV: transaction row
    SV-->>CT: Transaction domain object

    CT->>CT: ResponseSchema.dump(transaction)
    CT->>R: compat_success(data, status=201)
    R-->>C: 201 { data: {...}, meta: {...} }
```

## GraphQL — query autenticada (ex: listTransactions)

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant FL as Flask App
    participant MW as JWT Middleware
    participant GQL as GraphQL Controller\n(Ariadne)
    participant AUTH as graphql/auth.py\n(permission check)
    participant RES as Query Resolver
    participant SV as Domain Service
    participant DB as PostgreSQL

    C->>FL: POST /graphql  {query: "{ listTransactions(...) }"}  Bearer token
    FL->>MW: JWT validation (mesmo fluxo REST)
    MW->>FL: g.current_user = User(...)

    FL->>GQL: graphql_sync(schema, data, context_value={request})
    GQL->>AUTH: check_field_permission(info, "listTransactions")
    AUTH->>AUTH: Extrai user do context, verifica permissão
    alt Sem permissão
        AUTH-->>C: 403 { errors: [{message: "Forbidden"}] }
    end

    GQL->>RES: resolve_list_transactions(root, info, **kwargs)
    RES->>SV: get_transactions(user_id, filters)
    SV->>DB: SELECT ... (com selectinload para evitar N+1)
    DB-->>SV: rows
    SV-->>RES: [Transaction, ...]
    RES-->>GQL: serialized data
    GQL-->>C: 200 { data: { listTransactions: [...] } }
```

## Tratamento de erros — camadas

```mermaid
flowchart TD
    REQ[Request entra no Flask]
    MW{JWT válido?}
    VAL{Marshmallow\nvalid?}
    SVC{Service\nerro de negócio?}
    DB{DB/Redis\nerro?}
    OK[200/201 Success]
    E401[401 Unauthorized]
    E400[400 Bad Request\nerros de validação]
    E422[422 Unprocessable\nerro de negócio]
    E500[500 Internal Server Error\n+ log + AuditEvent]

    REQ --> MW
    MW -->|inválido| E401
    MW -->|válido| VAL
    VAL -->|inválido| E400
    VAL -->|válido| SVC
    SVC -->|DomainError| E422
    SVC -->|OK| DB
    DB -->|exception| E500
    DB -->|OK| OK
```
