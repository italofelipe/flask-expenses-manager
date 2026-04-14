from __future__ import annotations

import graphene

from app.graphql.mutations.auth import (
    ConfirmEmailMutation,
    ForgotPasswordMutation,
    LoginMutation,
    LogoutMutation,
    RegisterUserMutation,
    ResendConfirmationEmailMutation,
    ResetPasswordMutation,
    UpdateUserProfileMutation,
)
from app.graphql.mutations.budget import (
    CreateBudgetMutation,
    DeleteBudgetMutation,
    UpdateBudgetMutation,
)
from app.graphql.mutations.goal import (
    CreateGoalMutation,
    DeleteGoalMutation,
    SimulateGoalPlanMutation,
    UpdateGoalMutation,
)
from app.graphql.mutations.investment_operation import (
    AddInvestmentOperationMutation,
    DeleteInvestmentOperationMutation,
    UpdateInvestmentOperationMutation,
)
from app.graphql.mutations.notification import UpdateNotificationPreferencesMutation
from app.graphql.mutations.simulation import (
    CreateGoalFromInstallmentVsCashSimulationMutation,
    CreatePlannedExpenseFromInstallmentVsCashSimulationMutation,
    SaveInstallmentVsCashSimulationMutation,
)
from app.graphql.mutations.subscription import (
    CancelSubscriptionMutation,
    CreateCheckoutSessionMutation,
)
from app.graphql.mutations.ticker import AddTickerMutation, DeleteTickerMutation
from app.graphql.mutations.transaction import (
    CreateTransactionMutation,
    DeleteTransactionMutation,
    UpdateTransactionMutation,
)
from app.graphql.mutations.wallet import (
    AddWalletEntryMutation,
    DeleteWalletEntryMutation,
    UpdateWalletEntryMutation,
)

# ---------------------------------------------------------------------------
# H-P5.1 — REST/GraphQL ownership (issue #839)
#
# Deprecation policy per domain:
#   Auth        → REST-only. All auth/profile mutations deprecated.
#   Transactions → REST canonical. CRUD mutations deprecated.
#   Goals        → REST canonical. CRUD mutations deprecated.
#   Wallet       → REST canonical. CRUD mutations deprecated.
#
# Mutations NOT deprecated (no REST equivalent or GraphQL-specific value):
#   Tickers, Investment operations, Notification preferences,
#   Budget CRUD, Subscription management, Simulation flows.
#
# Sunset: 2026-12-31. After that, deprecated mutations will be removed.
# ---------------------------------------------------------------------------

_SUNSET = "Sunset: 2026-12-31."
_AUTH_DEPRECATION = f"Deprecated (H-P5.1): use REST instead. {_SUNSET}"
_TX_DEPRECATION = f"Deprecated (H-P5.1): use REST /transactions. {_SUNSET}"
_GOAL_DEPRECATION = f"Deprecated (H-P5.1): use REST /goals. {_SUNSET}"
_WALLET_DEPRECATION = f"Deprecated (H-P5.1): use REST /wallet/entries. {_SUNSET}"


class Mutation(graphene.ObjectType):
    # ── Auth domain (REST-only) ───────────────────────────────────────────────
    register_user = RegisterUserMutation.Field(
        deprecation_reason=f"Use REST POST /auth/register. {_AUTH_DEPRECATION}"
    )
    login = LoginMutation.Field(
        deprecation_reason=f"Use REST POST /auth/login. {_AUTH_DEPRECATION}"
    )
    logout = LogoutMutation.Field(
        deprecation_reason=f"Use REST POST /auth/logout. {_AUTH_DEPRECATION}"
    )
    forgot_password = ForgotPasswordMutation.Field(
        deprecation_reason=f"Use REST POST /auth/forgot-password. {_AUTH_DEPRECATION}"
    )
    resend_confirmation_email = ResendConfirmationEmailMutation.Field(
        deprecation_reason=(
            f"Use REST POST /auth/resend-confirmation. {_AUTH_DEPRECATION}"
        )
    )
    reset_password = ResetPasswordMutation.Field(
        deprecation_reason=f"Use REST POST /auth/reset-password. {_AUTH_DEPRECATION}"
    )
    confirm_email = ConfirmEmailMutation.Field(
        deprecation_reason=f"Use REST POST /auth/confirm-email. {_AUTH_DEPRECATION}"
    )
    update_user_profile = UpdateUserProfileMutation.Field(
        deprecation_reason=f"Use REST PATCH /user/profile. {_AUTH_DEPRECATION}"
    )

    # ── Transactions domain (REST canonical) ─────────────────────────────────
    create_transaction = CreateTransactionMutation.Field(
        deprecation_reason=f"Use REST POST /transactions. {_TX_DEPRECATION}"
    )
    update_transaction = UpdateTransactionMutation.Field(
        deprecation_reason=(f"Use REST PATCH /transactions/{{id}}. {_TX_DEPRECATION}")
    )
    delete_transaction = DeleteTransactionMutation.Field(
        deprecation_reason=(f"Use REST DELETE /transactions/{{id}}. {_TX_DEPRECATION}")
    )

    # ── Goals domain (REST canonical) ────────────────────────────────────────
    create_goal = CreateGoalMutation.Field(
        deprecation_reason=f"Use REST POST /goals. {_GOAL_DEPRECATION}"
    )
    update_goal = UpdateGoalMutation.Field(
        deprecation_reason=f"Use REST PATCH /goals/{{id}}. {_GOAL_DEPRECATION}"
    )
    delete_goal = DeleteGoalMutation.Field(
        deprecation_reason=f"Use REST DELETE /goals/{{id}}. {_GOAL_DEPRECATION}"
    )

    # ── Simulation (GraphQL + REST parity — kept, no deprecation) ────────────
    simulate_goal_plan = SimulateGoalPlanMutation.Field()
    save_installment_vs_cash_simulation = (
        SaveInstallmentVsCashSimulationMutation.Field()
    )
    create_goal_from_installment_vs_cash_simulation = (
        CreateGoalFromInstallmentVsCashSimulationMutation.Field()
    )
    create_planned_expense_from_installment_vs_cash_simulation = (
        CreatePlannedExpenseFromInstallmentVsCashSimulationMutation.Field()
    )

    # ── Wallet domain (REST canonical) ───────────────────────────────────────
    add_wallet_entry = AddWalletEntryMutation.Field(
        deprecation_reason=f"Use REST POST /wallet/entries. {_WALLET_DEPRECATION}"
    )
    update_wallet_entry = UpdateWalletEntryMutation.Field(
        deprecation_reason=(
            f"Use REST PATCH /wallet/entries/{{id}}. {_WALLET_DEPRECATION}"
        )
    )
    delete_wallet_entry = DeleteWalletEntryMutation.Field(
        deprecation_reason=(
            f"Use REST DELETE /wallet/entries/{{id}}. {_WALLET_DEPRECATION}"
        )
    )

    # ── Investment operations (GraphQL-only, no REST equivalent) ─────────────
    add_investment_operation = AddInvestmentOperationMutation.Field()
    update_investment_operation = UpdateInvestmentOperationMutation.Field()
    delete_investment_operation = DeleteInvestmentOperationMutation.Field()

    # ── Tickers (GraphQL-only, no REST equivalent) ───────────────────────────
    add_ticker = AddTickerMutation.Field()
    delete_ticker = DeleteTickerMutation.Field()

    # ── Budget (REST canonical, kept for GraphQL compat — review at sunset) ──
    create_budget = CreateBudgetMutation.Field()
    update_budget = UpdateBudgetMutation.Field()
    delete_budget = DeleteBudgetMutation.Field()

    # ── Subscription management ───────────────────────────────────────────────
    create_checkout_session = CreateCheckoutSessionMutation.Field()
    cancel_subscription = CancelSubscriptionMutation.Field()

    # ── Notification preferences (GraphQL-only) ───────────────────────────────
    update_notification_preferences = UpdateNotificationPreferencesMutation.Field()


__all__ = ["Mutation"]
