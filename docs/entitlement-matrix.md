# Entitlement Matrix

Source of truth for which REST endpoints and GraphQL operations require a premium
entitlement.  Updated whenever a new gated feature is added.

The `scripts/entitlement_coverage_check.py` CI gate enforces bidirectional
consistency: every entry here must have a matching `@require_entitlement` (or
`has_entitlement` guard) in the source, and every guard in the source must have a
matching entry here.

## REST Endpoints

| Method | Path | Entitlement | Minimum Plan | Controller |
|--------|------|-------------|--------------|------------|
| GET | `/transactions/export` | `export_pdf` | Premium / Trial | `app/controllers/transaction/export_resource.py` |
| POST | `/simulations/{id}/goal` | `advanced_simulations` | Premium / Trial | `app/controllers/simulation/installment_vs_cash_resources.py` |
| POST | `/simulations/{id}/planned-expense` | `advanced_simulations` | Premium / Trial | `app/controllers/simulation/installment_vs_cash_resources.py` |

## GraphQL Operations

| Operation | Type | Entitlement | Minimum Plan | Resolver |
|-----------|------|-------------|--------------|----------|
| `simulationToGoal` | mutation | `advanced_simulations` | Premium / Trial | `app/graphql/mutations/simulation.py` |
| `simulationToPlannedExpense` | mutation | `advanced_simulations` | Premium / Trial | `app/graphql/mutations/simulation.py` |

## Feature Key Reference

| Feature Key | Granted to | Revoked on |
|-------------|------------|------------|
| `export_pdf` | Premium, Trial | Downgrade to Free / cancellation |
| `advanced_simulations` | Premium, Trial | Downgrade to Free / cancellation |
| `shared_entries` | Premium, Trial | Downgrade to Free / cancellation |
| `focus_mode` | Premium, Trial | Downgrade to Free / cancellation |
| `basic_simulations` | Free, Premium, Trial | Never |
| `wallet_read` | Free, Premium, Trial | Never |

## Adding a New Gated Feature

1. Add `@require_entitlement("feature_key")` (REST) or call `has_entitlement()` (GraphQL)
2. Add the new feature key to `app/config/plan_features.py` under the appropriate plans
3. Add a row to the relevant table above
4. Run `python3 scripts/entitlement_coverage_check.py` — it must pass before committing
