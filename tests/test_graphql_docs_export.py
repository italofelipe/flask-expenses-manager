from __future__ import annotations

from app.graphql.authorization import (
    DEFAULT_GRAPHQL_PUBLIC_MUTATIONS,
    DEFAULT_GRAPHQL_PUBLIC_QUERIES,
)
from app.graphql.docs_catalog import (
    build_graphql_operations_manifest,
    get_graphql_operation_catalog,
    get_graphql_operation_names,
)
from app.graphql.docs_export import (
    build_graphql_docs_bundle,
    read_committed_graphql_docs_bundle,
)
from app.graphql.schema import schema


def test_docs_catalog_covers_runtime_root_fields() -> None:
    assert get_graphql_operation_names("query") == set(
        schema.graphql_schema.query_type.fields
    )
    assert get_graphql_operation_names("mutation") == set(
        schema.graphql_schema.mutation_type.fields
    )


def test_public_manifest_entries_match_authorization_defaults() -> None:
    manifest = build_graphql_operations_manifest()
    public_queries = {
        entry["name"]
        for entry in manifest
        if entry["operation_type"] == "query" and entry["access"] == "public"
    }
    public_mutations = {
        entry["name"]
        for entry in manifest
        if entry["operation_type"] == "mutation" and entry["access"] == "public"
    }
    assert public_queries == (set(DEFAULT_GRAPHQL_PUBLIC_QUERIES) - {"__typename"})
    assert public_mutations == set(DEFAULT_GRAPHQL_PUBLIC_MUTATIONS)


def test_premium_simulation_bridges_are_flagged() -> None:
    catalog = {
        operation.name: operation for operation in get_graphql_operation_catalog()
    }
    assert catalog["createGoalFromInstallmentVsCashSimulation"].entitlements == (
        "advanced_simulations",
    )
    assert catalog[
        "createPlannedExpenseFromInstallmentVsCashSimulation"
    ].entitlements == ("advanced_simulations",)


def test_dashboard_graphql_ownership_is_explicit_in_catalog() -> None:
    catalog = {
        operation.name: operation for operation in get_graphql_operation_catalog()
    }

    assert catalog["dashboardOverview"].domain == "dashboard"
    assert catalog["dashboardOverview"].source_module == "app.graphql.queries.dashboard"
    assert catalog["transactionDashboard"].domain == "dashboard"
    assert catalog["transactionDashboard"].source_module == (
        "app.graphql.queries.dashboard"
    )
    assert catalog["transactionDashboard"].legacy_alias_of == "dashboardOverview"


def test_committed_graphql_docs_match_runtime_bundle() -> None:
    generated = build_graphql_docs_bundle("runtime")
    committed = read_committed_graphql_docs_bundle()
    assert committed == generated


def test_h_p5_1_deprecated_mutations_are_marked_in_schema() -> None:
    """H-P5.1: REST canonical mutations must be marked as deprecated in the schema."""
    mutation_type = schema.graphql_schema.mutation_type
    assert mutation_type is not None

    # Auth domain (REST-only): all auth/profile mutations deprecated.
    auth_deprecated = {
        "registerUser",
        "login",
        "logout",
        "forgotPassword",
        "resendConfirmationEmail",
        "resetPassword",
        "confirmEmail",
        "updateUserProfile",
    }
    # Transactions / Goals / Wallet (REST canonical): CRUD mutations deprecated.
    rest_canonical_deprecated = {
        "createTransaction",
        "updateTransaction",
        "deleteTransaction",
        "createGoal",
        "updateGoal",
        "deleteGoal",
        "addWalletEntry",
        "updateWalletEntry",
        "deleteWalletEntry",
    }
    expected_deprecated = auth_deprecated | rest_canonical_deprecated

    fields = mutation_type.fields
    for name in expected_deprecated:
        assert name in fields, f"Mutation '{name}' not found in schema"
        field = fields[name]
        assert field.deprecation_reason, (
            f"Mutation '{name}' must have a deprecation_reason (H-P5.1)"
        )

    # Mutations that should NOT be deprecated.
    not_deprecated = {
        "addTicker",
        "deleteTicker",
        "addInvestmentOperation",
        "updateInvestmentOperation",
        "deleteInvestmentOperation",
        "updateNotificationPreferences",
    }
    for name in not_deprecated:
        assert name in fields, f"Mutation '{name}' not found in schema"
        field = fields[name]
        assert not field.deprecation_reason, (
            f"Mutation '{name}' should NOT be deprecated"
        )
