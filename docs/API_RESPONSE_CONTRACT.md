# API Response Contract (Fase 0)

Status: especificação de referência para adoção gradual.

Objetivo:
- padronizar respostas de sucesso e erro
- manter compatibilidade durante migração
- facilitar testes, observabilidade e consumo por frontend

## Princípios
- Um envelope único para todas as respostas JSON.
- `success` indica resultado sem depender do status code.
- `data` contém payload de domínio.
- `error` contém erro estruturado quando houver falha.
- `meta` contém paginação/correlação/detalhes técnicos não funcionais.

## Envelope padrão

## Sucesso
```json
{
  "success": true,
  "message": "Transação criada com sucesso",
  "data": {},
  "meta": {
    "request_id": "uuid-opcional"
  }
}
```

## Erro
```json
{
  "success": false,
  "message": "Erro de validação",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "field": ["mensagem"]
    }
  },
  "meta": {
    "request_id": "uuid-opcional"
  }
}
```

## Campos
- `success` (`bool`): obrigatório.
- `message` (`string`): obrigatório, orientado ao cliente.
- `data` (`object|array|null`): obrigatório em sucesso; opcional em erro.
- `error` (`object|null`): obrigatório em erro; ausente em sucesso.
- `meta` (`object`): opcional.

## Catálogo de códigos de erro (proposto)
- `VALIDATION_ERROR` -> 400
- `UNAUTHORIZED` -> 401
- `FORBIDDEN` -> 403
- `NOT_FOUND` -> 404
- `CONFLICT` -> 409
- `UNPROCESSABLE_ENTITY` -> 422
- `INTERNAL_ERROR` -> 500
- `EXTERNAL_PROVIDER_ERROR` -> 502/503

## Contrato de paginação (proposto)
Para endpoints paginados, usar:

```json
{
  "success": true,
  "message": "Lista retornada com sucesso",
  "data": {
    "items": []
  },
  "meta": {
    "pagination": {
      "page": 1,
      "per_page": 10,
      "total": 100,
      "pages": 10
    }
  }
}
```

## Contrato para validação de campo

```json
{
  "success": false,
  "message": "Erro de validação",
  "error": {
    "code": "VALIDATION_ERROR",
    "details": {
      "email": ["Not a valid email address."],
      "password": ["A senha deve ter no mínimo 10 caracteres..."]
    }
  }
}
```

## Estratégia de migração sem quebra
1. Curto prazo: manter payload atual e adicionar envelope só em novos endpoints.
2. Médio prazo: adicionar feature-flag/header para novo contrato (`X-API-Contract: v2`).
3. Longo prazo: unificar 100% das respostas em envelope padrão.

## Critérios de adoção por endpoint
- Endpoint documentado com exemplos de sucesso/erro.
- Teste de contrato cobrindo campos obrigatórios.
- Mapeamento explícito de exceptions para `error.code`.
