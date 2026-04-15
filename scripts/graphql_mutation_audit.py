#!/usr/bin/env python3
"""CI gate: enforce GraphQL/REST ownership per ADR-0002.

Verifies that all CRUD mutations listed in ADR-0002 have a deprecation_reason
set in app/graphql/mutations/__init__.py. Fails if any of the required mutations
are missing the deprecation marker, preventing silent regressions.

Rules (from docs/adr/0002-graphql-ownership.md):
  - REST is the canonical surface for CRUD operations.
  - GraphQL mutations for CRUD of domain entities must carry deprecation_reason.
  - New CRUD mutations without deprecation_reason are forbidden.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MUTATIONS_INIT = ROOT / "app/graphql/mutations/__init__.py"

# Mutations that MUST have a deprecation_reason per ADR-0002.
# Any new CRUD mutation added here without deprecation_reason will fail CI.
ADR_0002_CRUD_MUTATIONS: set[str] = {
    "create_transaction",
    "update_transaction",
    "delete_transaction",
    "create_goal",
    "update_goal",
    "delete_goal",
    "add_wallet_entry",
    "update_wallet_entry",
    "delete_wallet_entry",
    "add_investment_operation",
    "update_investment_operation",
    "delete_investment_operation",
    "create_budget",
    "update_budget",
    "delete_budget",
}

# Mutations that match CRUD verb patterns but are ALLOWED without deprecation:
# - No REST equivalent exists (ticker, notification) OR
# - They are auth-specific (update_user_profile) OR
# - They are simulation composite operations (no canonical REST resource)
ADR_0002_ALLOWED_CRUD_VERBS: set[str] = {
    "add_ticker",  # No REST equivalent — GraphQL-only ticker management
    "delete_ticker",  # No REST equivalent — GraphQL-only ticker management
    "update_user_profile",  # Auth-domain, no REST CRUD equivalent
    "update_notification_preferences",  # No REST equivalent
    "create_goal_from_installment_vs_cash_simulation",  # Simulation composite
    "create_planned_expense_from_installment_vs_cash_simulation",  # Simulation
    "create_checkout_session",  # Stripe-specific, no domain CRUD equivalent
}

# Keywords that, if present in a mutation name without deprecation, indicate
# a likely-new CRUD mutation that should be flagged for ADR-0002 review.
CRUD_VERBS = ("create_", "update_", "delete_", "add_", "remove_", "patch_")


def _parse_mutation_class(source: str) -> dict[str, bool]:
    """Return {mutation_field_name: has_deprecation_reason} for the Mutation class."""
    tree = ast.parse(source)
    result: dict[str, bool] = {}

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef) or node.name != "Mutation":
            continue
        for stmt in node.body:
            if not isinstance(stmt, ast.Assign):
                continue
            for target in stmt.targets:
                if not isinstance(target, ast.Name):
                    continue
                field_name = target.id
                call = stmt.value
                if not isinstance(call, ast.Call):
                    continue
                has_dep = any(
                    isinstance(kw, ast.keyword) and kw.arg == "deprecation_reason"
                    for kw in call.keywords
                )
                result[field_name] = has_dep

    return result


def main() -> int:
    source = MUTATIONS_INIT.read_text(encoding="utf-8")
    mutations = _parse_mutation_class(source)

    failures: list[str] = []

    # 1. Check that all ADR-0002 CRUD mutations have deprecation_reason
    for name in sorted(ADR_0002_CRUD_MUTATIONS):
        if name not in mutations:
            failures.append(
                f"  MISSING field '{name}' — should exist in Mutation class"
            )
        elif not mutations[name]:
            failures.append(
                f"  MISSING deprecation_reason on '{name}' "
                f"(ADR-0002 requires it — see docs/adr/0002-graphql-ownership.md)"
            )

    # 2. Detect new CRUD mutations not in ADR-0002 list and not deprecated
    for name, has_dep in mutations.items():
        if name in ADR_0002_CRUD_MUTATIONS:
            continue
        if name in ADR_0002_ALLOWED_CRUD_VERBS:
            continue
        if any(name.startswith(verb) for verb in CRUD_VERBS) and not has_dep:
            failures.append(
                f"  NEW CRUD mutation '{name}' lacks deprecation_reason. "
                f"Per ADR-0002, new CRUD mutations must be deprecated with "
                f"a pointer to the REST equivalent, or added to "
                f"ADR_0002_ALLOWED_CRUD_VERBS in this script "
                f"if no REST equivalent exists."
            )

    if failures:
        print(
            "graphql-mutation-audit FAILED — ADR-0002 violation(s) detected:",
            file=sys.stderr,
        )
        for f in failures:
            print(f, file=sys.stderr)
        print(
            "\nSee docs/adr/0002-graphql-ownership.md for the rule.",
            file=sys.stderr,
        )
        return 1

    print(
        f"[graphql-mutation-audit] ok — {len(ADR_0002_CRUD_MUTATIONS)} CRUD mutations "
        f"correctly deprecated, {len(mutations) - len(ADR_0002_CRUD_MUTATIONS)} "
        f"non-CRUD mutations allowed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
