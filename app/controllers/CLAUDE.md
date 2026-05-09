# CLAUDE.md — `app/controllers/*`

Camada REST do auraxis-api. Cada controller e um adapter que:
1. Valida a request com Marshmallow schema
2. Chama o service da camada de aplicacao
3. Serializa a response

## Estrutura canonica por controller

```python
# app/controllers/<domain>_controller.py
from flask import Blueprint, request, jsonify
from app.schemas.<domain>_schema import <Domain>Schema
from app.application.services.<domain>_service import <Domain>Service

bp = Blueprint('<domain>', __name__)

@bp.route('/<domain>', methods=['POST'])
@require_auth   # sempre aplicar auth
def create_<domain>():
    data = <Domain>Schema().load(request.json)  # valida + deserializa
    result = <Domain>Service.create(data)        # logica de negocio
    return jsonify(<Domain>Schema().dump(result)), 201
```

## Regras

- Controllers nao contem logica de negocio — apenas orchestracao HTTP
- Toda validacao via Marshmallow schemas (em `app/schemas/`)
- Toda logica de negocio em `app/application/services/`
- Autenticacao via decorator `@require_auth` (sempre)
- Erros de dominio → HTTP errors via `AppError` hierarchy
- Response format padrao: use `response_contract.py` para envelope consistente

## Controllers existentes

| Controller | Dominio | Blueprint prefix |
|---|---|---|
| `auth_controller.py` | Auth/sessao | `/auth` |
| `user_controller.py` | Perfil de usuario | `/user` |
| `transaction_controller.py` | Transacoes financeiras | `/transactions` |
| `goal_controller.py` | Metas financeiras | `/goals` |
| `wallet_controller.py` | Carteira/investimentos | `/wallet` |
| `subscription_controller.py` | Assinatura/billing | `/subscription` |
| `budget_controller.py` (em `budget/`) | Orcamentos por envelope | `/budget` |
| `alert_controller.py` | Alertas e notificacoes | `/alerts` |
| `graphql_controller.py` | Endpoint GraphQL unificado | `/graphql` |
| `health_controller.py` | Healthcheck da API | `/health` |
| `simulation_controller.py` | Simulacoes financeiras | `/simulation` |
| `observability_controller.py` | Metricas e tracing | `/observability` |

## REST vs GraphQL

Decisao governada por `docs/adr/0002-graphql-ownership.md`:

- **REST**: operacoes de escrita (POST, PUT, PATCH, DELETE) e endpoints publicos
- **GraphQL**: queries complexas, dados relacionados em uma unica request
- Todo endpoint REST deve ter equivalente GraphQL quando for query de dados

## O que perguntar antes (nao agir autonomamente)

- Adicionar novo endpoint que mude contratos REST (impacta consumers auraxis-web e auraxis-app)
- Modificar formato de response de endpoint existente (quebra contratos)
- Adicionar novo decorator de auth ou middleware global

## Testes

Todo controller deve ter testes de integracao em `tests/integration/`:

```bash
pytest tests/integration/test_<domain>_controller.py -v
```

Cobertura minima: 85% (obrigatoria para merge).
