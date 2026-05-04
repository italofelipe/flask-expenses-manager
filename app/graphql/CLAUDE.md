# CLAUDE.md — GraphQL Module

## Stack

GraphQL is implemented with **Graphene 3** (not Ariadne). Entry point: `app/graphql/schema.py`.

## Auth policy — mandatory for every new resolver

Every new mutation and non-public query **must** call `get_current_user_required()` as its first
line, or be added to the explicit public allowlist in `app/graphql/authorization.py`.

There is a parameterized regression test (`tests/test_graphql_auth_everywhere.py`) that
enumerates all mutations and queries at runtime and asserts that any operation not in the
allowlist requires auth. A new resolver that bypasses this will cause CI to fail.

Adding to the allowlist requires a deliberate review comment explaining why the operation is public.

## Module layout

```
app/graphql/
  complexity/
    __init__.py
    analyzer.py      — AST traversal: depth, complexity, fragment resolution
    policy.py        — GraphQLSecurityPolicy + env loaders + GraphQLSecurityViolation
  mutations/         — one file per domain (transaction, goal, wallet, ...)
  queries/           — one file per domain
  auth.py            — get_current_user_required / get_current_user_optional
  authorization.py   — GraphQLAuthorizationPolicy + enforce_graphql_authorization
  decorators.py      — (planned) @resolver_with_user_context, @graphql_error_adapter
  enums.py           — WalletAssetClassEnum and other domain enums
  errors.py          — build_public_graphql_error, PUBLIC_GRAPHQL_ERROR_CODES
  introspection_policy.py — enforce_introspection_policy
  observability.py   — log_graphql_resolver decorator
  scalars.py         — DecimalScalar
  security.py        — thin facade: analyze_graphql_query + re-exports
  schema.py          — Schema assembly
  types.py           — shared output types (payload types, pagination)
```

## Resolver conventions

1. Call `get_current_user_required()` first (or add to allowlist with justification).
2. Instantiate the service: `service = XxxService.with_defaults(user.id)`.
3. Wrap service calls in `try/except` and convert domain exceptions via `build_public_graphql_error`.
4. Return a typed payload object — never a raw dict.

## Complexity limits (env-configurable)

| Env var | Default | Purpose |
|---------|---------|---------|
| `GRAPHQL_MAX_QUERY_BYTES` | 20 000 | Request size guard |
| `GRAPHQL_MAX_DEPTH` | 8 | AST nesting depth |
| `GRAPHQL_MAX_COMPLEXITY` | 300 | Weighted field count |
| `GRAPHQL_MAX_OPERATIONS` | 3 | Operations per document |
| `GRAPHQL_MAX_LIST_MULTIPLIER` | 50 | Multiplier for list fields |
| `GRAPHQL_ALLOW_INTROSPECTION` | false (prod) | Enable schema introspection |
