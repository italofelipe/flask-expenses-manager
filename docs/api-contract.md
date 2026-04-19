# Auraxis API Response Contract

Reference specification for all JSON responses served by the Auraxis REST API.

---

## 1. Versioning

The response format is negotiated via request header:

| Header | Value | Behaviour |
|--------|-------|-----------|
| `X-API-Contract` | `v2` | Returns structured `{"success", "message", "data", "meta"}` envelope |
| `X-API-Contract` | `v3` | Same envelope as v2 (reserved for future extension) |
| *(absent)* | — | Legacy format — raw dict, varies per endpoint |

Clients should always send `X-API-Contract: v2` to receive the canonical
envelope.

---

## 2. Success Envelope

```json
{
  "success": true,
  "message": "Human-readable success message",
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 85,
    "pages": 5
  }
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `success` | `boolean` | yes | Always `true` for 2xx responses |
| `message` | `string` | yes | Localised confirmation message |
| `data` | `object \| array \| null` | yes | Domain payload (see section 5) |
| `meta` | `object` | no | Non-domain metadata (pagination, correlation IDs, etc.) |

---

## 3. Error Envelope

HTTP 4xx and 5xx responses return:

```json
{
  "success": false,
  "message": "Human-readable error description",
  "error": {
    "code": "MACHINE_READABLE_CODE",
    "details": { ... }
  }
}
```

| Field | Type | Description |
|-------|------|-------------|
| `success` | `boolean` | Always `false` |
| `message` | `string` | Error description for display |
| `error.code` | `string` | Machine-readable code (UPPER_SNAKE_CASE) |
| `error.details` | `object` | Optional validation messages or extra context |

### Common error codes

| Code | HTTP status | Meaning |
|------|-------------|---------|
| `VALIDATION_ERROR` | 400 | Payload failed schema validation |
| `BAD_REQUEST` | 400 | Malformed request |
| `UNAUTHORIZED` | 401 | Missing or invalid authentication |
| `FORBIDDEN` | 403 | Authenticated but lacks permission |
| `NOT_FOUND` | 404 | Resource not found |
| `CONFLICT` | 409 | State conflict (e.g. duplicate) |
| `INTERNAL_ERROR` | 500 | Unhandled server error |

---

## 4. Field Naming Convention

All JSON keys use **snake_case** throughout (request bodies and response
payloads).

```json
{ "due_date": "2026-04-19", "installment_count": 12 }
```

Date values follow ISO 8601: `YYYY-MM-DD`.
Datetime values follow ISO 8601 with UTC suffix: `2026-04-19T14:30:00`.
Monetary amounts are serialised as **strings** with two decimal places to
preserve precision: `"1234.56"`.

---

## 5. Pagination

List endpoints accept query-string parameters and include pagination metadata
inside `meta`:

### Request parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `page` | `1` | 1-based page number |
| `per_page` | `20` | Page size (max 100) |

### Response `meta` keys

```json
{
  "meta": {
    "total": 85,
    "page": 1,
    "per_page": 20,
    "pages": 5
  }
}
```

| Key | Type | Description |
|-----|------|-------------|
| `total` | `integer` | Total number of records across all pages |
| `page` | `integer` | Current page number |
| `per_page` | `integer` | Number of items per page |
| `pages` | `integer` | Total number of pages |

---

## 6. Controller Implementation Reference

Controllers use helpers from `app/controllers/response_contract.py`:

```python
from app.controllers.response_contract import (
    compat_success_response,
    compat_error_response,
    compat_success_tuple,
    compat_error_tuple,
)
```

`compat_*` functions return the legacy payload when no `X-API-Contract`
header is present, and the structured envelope when `v2`/`v3` is requested.
This allows incremental migration without breaking existing clients.

---

## 7. Deprecation Headers

Endpoints scheduled for removal include the following HTTP headers:

| Header | Example | Meaning |
|--------|---------|---------|
| `Deprecation` | `true` | Endpoint is deprecated |
| `Sunset` | `Tue, 30 Jun 2026 23:59:59 GMT` | Removal date |
| `X-Auraxis-Successor-Endpoint` | `/api/v2/transactions` | Replacement URL |
| `X-Auraxis-Successor-Method` | `GET` | HTTP method of replacement |

---

## 8. Sensitive Field Filtering

The following field names are automatically stripped from response payloads
in all environments:

- `password`
- `password_hash`
- `secret`
- `secret_key`
- `jwt_secret_key`

This filtering is applied inside `success_payload()` in
`app/utils/response_builder.py`.
