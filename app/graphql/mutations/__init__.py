from __future__ import annotations

import graphene

from app.graphql.mutations.auth import (
    ForgotPasswordMutation,
    LoginMutation,
    LogoutMutation,
    RegisterUserMutation,
    ResetPasswordMutation,
    UpdateUserProfileMutation,
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
from app.graphql.mutations.ticker import AddTickerMutation, DeleteTickerMutation
from app.graphql.mutations.transaction import (
    CreateTransactionMutation,
    DeleteTransactionMutation,
)
from app.graphql.mutations.wallet import (
    AddWalletEntryMutation,
    DeleteWalletEntryMutation,
    UpdateWalletEntryMutation,
)


class Mutation(graphene.ObjectType):
    register_user = RegisterUserMutation.Field()
    login = LoginMutation.Field()
    logout = LogoutMutation.Field()
    forgot_password = ForgotPasswordMutation.Field()
    reset_password = ResetPasswordMutation.Field()
    update_user_profile = UpdateUserProfileMutation.Field()
    create_transaction = CreateTransactionMutation.Field()
    delete_transaction = DeleteTransactionMutation.Field()
    create_goal = CreateGoalMutation.Field()
    update_goal = UpdateGoalMutation.Field()
    delete_goal = DeleteGoalMutation.Field()
    simulate_goal_plan = SimulateGoalPlanMutation.Field()
    add_wallet_entry = AddWalletEntryMutation.Field()
    update_wallet_entry = UpdateWalletEntryMutation.Field()
    delete_wallet_entry = DeleteWalletEntryMutation.Field()
    add_investment_operation = AddInvestmentOperationMutation.Field()
    update_investment_operation = UpdateInvestmentOperationMutation.Field()
    delete_investment_operation = DeleteInvestmentOperationMutation.Field()
    add_ticker = AddTickerMutation.Field()
    delete_ticker = DeleteTickerMutation.Field()


__all__ = ["Mutation"]
