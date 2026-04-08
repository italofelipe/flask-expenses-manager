# mypy Strict Migration — ARC-10

Tracks the phased removal of `disable_error_code = ["untyped-decorator"]`
overrides from `pyproject.toml`.

## Status

| Fase | Modules | Status |
|------|---------|--------|
| Fase 1+2 | 13 modules (Flask/Click/JWT decorators) | ✅ Done — overrides removed |
| Fase 3 | 8 modules (schemas + controllers) | 🔲 Pending |

---

## Fase 1+2 — Completed

**Finding:** All 13 modules were already clean under strict mode.
The override was suppressing errors that did not actually occur —
flask-stubs, click-stubs, and flask-jwt-extended-stubs already annotate
the framework decorators (`@app.after_request`, `@app.before_request`,
`@app.errorhandler`, `@jwt.*`, `@click.option`, `@app.cli.group`).

**Modules removed from override:**

| Module | Decorators affected |
|--------|---------------------|
| `app.middleware.security_headers` | `@app.after_request` |
| `app.middleware.cors` | `@app.after_request`, `@app.before_request` |
| `app.http.request_context` | `@app.before_request`, `@app.after_request` |
| `app.middleware.docs_access` | `@app.before_request` |
| `app.extensions.audit_trail` | `@app.after_request` |
| `app.extensions.http_observability` | `@app.before_request`, `@app.after_request` |
| `app.controllers.health_controller` | Blueprint `@get` routes |
| `app.extensions.integration_metrics_cli` | `@app.cli.group`, `@command`, `@click.option` |
| `app.extensions.audit_retention_cli` | `@app.cli.group`, `@command`, `@click.option` |
| `app.extensions.jwt_callbacks` | `@jwt.*_loader` decorators |
| `app.extensions.error_handlers` | `@app.errorhandler` |
| `app.extensions.prometheus_metrics` | `@app.before_request`, `@app.after_request` |
| `app.controllers.observability_controller` | Blueprint `@get` routes |

---

## Fase 3 — Pending

**Remaining overrides** (8 modules):

### `app.schemas.*` — Marshmallow schemas

- **Issue:** `@pre_load`, `@post_load`, `@validates`, `@validates_schema`
  decorators from Marshmallow lack stubs that mypy accepts in strict mode.
- **Scope:** ~20+ schema files × 3-5 decorators each ≈ 60-100 locations.
- **Options:**
  1. Create `marshmallow.pyi` stubs for the decorator types.
  2. Add `# type: ignore[misc]` per decorator (high churn).
  3. Migrate schemas to Pydantic (long-term, breaks API contract).
- **Recommendation:** Create stubs — one file solves all schema files.
- **Blocker:** Needs dedicated schema refactor session.

### `app.controllers.subscription_controller`
- **Issue:** Mix of `@subscription_bp.route` + `@typed_jwt_required` decorators.
- **Fix:** Ensure `typed_jwt_required` in `app/utils/typed_decorators.py` has
  a proper `ParamSpec`-based overload so mypy can infer the decorated
  function's signature. Then inline ignores for blueprint routes if needed.

### `app.controllers.shared_entries.resources`
### `app.controllers.fiscal.resources`
### `app.controllers.wallet.valuation_resources`
### `app.controllers.wallet.operation_resources`
### `app.controllers.wallet.entry_resources`
- **Issue:** Same pattern as subscription_controller — `typed_jwt_required` +
  `@doc` + blueprint route decorators.
- **Fix:** Fix `typed_decorators.py` once → removes override for all 5 modules.

### `app.controllers.auth.error_handlers`
- **Issue:** `@parser.error_handler` (webargs) lacks type stub.
- **Fix:** Add `# type: ignore[misc]` to the single affected line.
- **Effort:** 5 minutes — lowest priority of remaining modules.

---

## CI enforcement

Once Fase 3 is complete, the `[[tool.mypy.overrides]]` block will be removed
entirely. At that point add a CI step:

```yaml
- name: No new type: ignore without justification
  run: |
    python scripts/ci/check_type_ignores.py --max-count=$(cat .type_ignore_baseline)
```

This prevents regression — new `# type: ignore` additions require an updated
baseline with a justification comment.
