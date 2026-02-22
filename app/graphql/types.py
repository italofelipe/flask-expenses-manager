from __future__ import annotations

import graphene


class UserType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    email = graphene.String(required=True)
    gender = graphene.String()
    birth_date = graphene.String()
    monthly_income = graphene.Float()
    monthly_income_net = graphene.Float()
    net_worth = graphene.Float()
    monthly_expenses = graphene.Float()
    initial_investment = graphene.Float()
    monthly_investment = graphene.Float()
    investment_goal_date = graphene.String()
    state_uf = graphene.String()
    occupation = graphene.String()
    investor_profile = graphene.String()
    financial_objectives = graphene.String()


class AuthPayloadType(graphene.ObjectType):
    token = graphene.String()
    user = graphene.Field(UserType)
    message = graphene.String(required=True)


class TransactionTypeObject(graphene.ObjectType):
    id = graphene.ID(required=True)
    title = graphene.String(required=True)
    amount = graphene.String(required=True)
    type = graphene.String(required=True)
    due_date = graphene.String(required=True)
    start_date = graphene.String()
    end_date = graphene.String()
    description = graphene.String()
    observation = graphene.String()
    is_recurring = graphene.Boolean(required=True)
    is_installment = graphene.Boolean(required=True)
    installment_count = graphene.Int()
    tag_id = graphene.String()
    account_id = graphene.String()
    credit_card_id = graphene.String()
    status = graphene.String(required=True)
    currency = graphene.String(required=True)
    created_at = graphene.String()
    updated_at = graphene.String()


class PaginationType(graphene.ObjectType):
    total = graphene.Int(required=True)
    page = graphene.Int(required=True)
    per_page = graphene.Int(required=True)
    pages = graphene.Int()


class TransactionListPayloadType(graphene.ObjectType):
    items = graphene.List(TransactionTypeObject, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class TransactionSummaryPayloadType(graphene.ObjectType):
    month = graphene.String(required=True)
    income_total = graphene.Float(required=True)
    expense_total = graphene.Float(required=True)
    items = graphene.List(TransactionTypeObject, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class TransactionDueCountsType(graphene.ObjectType):
    total_transactions = graphene.Int(required=True)
    income_transactions = graphene.Int(required=True)
    expense_transactions = graphene.Int(required=True)


class TransactionDueRangePayloadType(graphene.ObjectType):
    items = graphene.List(TransactionTypeObject, required=True)
    counts = graphene.Field(TransactionDueCountsType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class DashboardStatusCountsType(graphene.ObjectType):
    paid = graphene.Int(required=True)
    pending = graphene.Int(required=True)
    cancelled = graphene.Int(required=True)
    postponed = graphene.Int(required=True)
    overdue = graphene.Int(required=True)


class DashboardCountsType(graphene.ObjectType):
    total_transactions = graphene.Int(required=True)
    income_transactions = graphene.Int(required=True)
    expense_transactions = graphene.Int(required=True)
    status = graphene.Field(DashboardStatusCountsType, required=True)


class DashboardTotalsType(graphene.ObjectType):
    income_total = graphene.Float(required=True)
    expense_total = graphene.Float(required=True)
    balance = graphene.Float(required=True)


class DashboardCategoryType(graphene.ObjectType):
    tag_id = graphene.String()
    category_name = graphene.String(required=True)
    total_amount = graphene.Float(required=True)
    transactions_count = graphene.Int(required=True)


class DashboardCategoriesType(graphene.ObjectType):
    expense = graphene.List(DashboardCategoryType, required=True)
    income = graphene.List(DashboardCategoryType, required=True)


class TransactionDashboardPayloadType(graphene.ObjectType):
    month = graphene.String(required=True)
    totals = graphene.Field(DashboardTotalsType, required=True)
    counts = graphene.Field(DashboardCountsType, required=True)
    top_categories = graphene.Field(DashboardCategoriesType, required=True)


class GoalTypeObject(graphene.ObjectType):
    id = graphene.ID(required=True)
    title = graphene.String(required=True)
    description = graphene.String()
    category = graphene.String()
    target_amount = graphene.String(required=True)
    current_amount = graphene.String(required=True)
    priority = graphene.Int(required=True)
    target_date = graphene.String()
    status = graphene.String(required=True)
    created_at = graphene.String()
    updated_at = graphene.String()


class GoalListPayloadType(graphene.ObjectType):
    items = graphene.List(GoalTypeObject, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class GoalRecommendationType(graphene.ObjectType):
    priority = graphene.String(required=True)
    title = graphene.String(required=True)
    action = graphene.String(required=True)
    estimated_date = graphene.String()


class GoalPlanType(graphene.ObjectType):
    horizon = graphene.String(required=True)
    remaining_amount = graphene.String(required=True)
    capacity_amount = graphene.String(required=True)
    projected_monthly_contribution = graphene.String(required=True)
    recommended_monthly_contribution = graphene.String(required=True)
    months_to_goal = graphene.Int()
    months_until_target_date = graphene.Int()
    estimated_completion_date = graphene.String()
    target_date = graphene.String()
    goal_health = graphene.String(required=True)
    recommendations = graphene.List(GoalRecommendationType, required=True)


class WalletType(graphene.ObjectType):
    id = graphene.ID(required=True)
    name = graphene.String(required=True)
    value = graphene.Float()
    estimated_value_on_create_date = graphene.Float()
    ticker = graphene.String()
    quantity = graphene.Int()
    asset_class = graphene.String(required=True)
    annual_rate = graphene.Float()
    register_date = graphene.String(required=True)
    target_withdraw_date = graphene.String()
    should_be_on_wallet = graphene.Boolean(required=True)


class WalletHistoryItemType(graphene.ObjectType):
    original_quantity = graphene.Float()
    original_value = graphene.Float()
    change_type = graphene.String()
    change_date = graphene.String()


class WalletHistoryPayloadType(graphene.ObjectType):
    items = graphene.List(WalletHistoryItemType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class WalletListPayloadType(graphene.ObjectType):
    items = graphene.List(WalletType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class InvestmentOperationType(graphene.ObjectType):
    id = graphene.ID(required=True)
    wallet_id = graphene.ID(required=True)
    user_id = graphene.ID(required=True)
    operation_type = graphene.String(required=True)
    quantity = graphene.String(required=True)
    unit_price = graphene.String(required=True)
    fees = graphene.String(required=True)
    executed_at = graphene.String(required=True)
    notes = graphene.String()
    created_at = graphene.String()
    updated_at = graphene.String()


class InvestmentOperationListPayloadType(graphene.ObjectType):
    items = graphene.List(InvestmentOperationType, required=True)
    pagination = graphene.Field(PaginationType, required=True)


class InvestmentOperationSummaryType(graphene.ObjectType):
    total_operations = graphene.Int(required=True)
    buy_operations = graphene.Int(required=True)
    sell_operations = graphene.Int(required=True)
    buy_quantity = graphene.String(required=True)
    sell_quantity = graphene.String(required=True)
    net_quantity = graphene.String(required=True)
    gross_buy_amount = graphene.String(required=True)
    gross_sell_amount = graphene.String(required=True)
    average_buy_price = graphene.String(required=True)
    total_fees = graphene.String(required=True)


class InvestmentPositionType(graphene.ObjectType):
    total_operations = graphene.Int(required=True)
    buy_operations = graphene.Int(required=True)
    sell_operations = graphene.Int(required=True)
    total_buy_quantity = graphene.String(required=True)
    total_sell_quantity = graphene.String(required=True)
    current_quantity = graphene.String(required=True)
    current_cost_basis = graphene.String(required=True)
    average_cost = graphene.String(required=True)


class InvestmentInvestedAmountType(graphene.ObjectType):
    date = graphene.String(required=True)
    total_operations = graphene.Int(required=True)
    buy_operations = graphene.Int(required=True)
    sell_operations = graphene.Int(required=True)
    buy_amount = graphene.String(required=True)
    sell_amount = graphene.String(required=True)
    net_invested_amount = graphene.String(required=True)


class PortfolioValuationItemType(graphene.ObjectType):
    investment_id = graphene.ID(required=True)
    name = graphene.String(required=True)
    asset_class = graphene.String(required=True)
    annual_rate = graphene.String()
    ticker = graphene.String()
    should_be_on_wallet = graphene.Boolean(required=True)
    quantity = graphene.String(required=True)
    unit_price = graphene.String(required=True)
    invested_amount = graphene.String(required=True)
    current_value = graphene.String(required=True)
    profit_loss_amount = graphene.String(required=True)
    profit_loss_percent = graphene.String(required=True)
    market_price = graphene.String()
    valuation_source = graphene.String(required=True)
    uses_operations_quantity = graphene.Boolean(required=True)


class PortfolioValuationSummaryType(graphene.ObjectType):
    total_investments = graphene.Int(required=True)
    with_market_data = graphene.Int(required=True)
    without_market_data = graphene.Int(required=True)
    total_invested_amount = graphene.String(required=True)
    total_current_value = graphene.String(required=True)
    total_profit_loss = graphene.String(required=True)
    total_profit_loss_percent = graphene.String(required=True)


class PortfolioValuationPayloadType(graphene.ObjectType):
    summary = graphene.Field(PortfolioValuationSummaryType, required=True)
    items = graphene.List(PortfolioValuationItemType, required=True)


class PortfolioHistoryItemType(graphene.ObjectType):
    date = graphene.String(required=True)
    total_operations = graphene.Int(required=True)
    buy_operations = graphene.Int(required=True)
    sell_operations = graphene.Int(required=True)
    buy_amount = graphene.String(required=True)
    sell_amount = graphene.String(required=True)
    net_invested_amount = graphene.String(required=True)
    cumulative_net_invested = graphene.String(required=True)
    total_current_value_estimate = graphene.String(required=True)
    total_profit_loss_estimate = graphene.String(required=True)


class PortfolioHistorySummaryType(graphene.ObjectType):
    start_date = graphene.String(required=True)
    end_date = graphene.String(required=True)
    total_points = graphene.Int(required=True)
    total_buy_amount = graphene.String(required=True)
    total_sell_amount = graphene.String(required=True)
    total_net_invested_amount = graphene.String(required=True)
    final_cumulative_net_invested = graphene.String(required=True)
    final_total_current_value_estimate = graphene.String(required=True)
    final_total_profit_loss_estimate = graphene.String(required=True)


class PortfolioHistoryPayloadType(graphene.ObjectType):
    summary = graphene.Field(PortfolioHistorySummaryType, required=True)
    items = graphene.List(PortfolioHistoryItemType, required=True)


class TickerType(graphene.ObjectType):
    id = graphene.ID(required=True)
    symbol = graphene.String(required=True)
    quantity = graphene.Float(required=True)
    type = graphene.String()
