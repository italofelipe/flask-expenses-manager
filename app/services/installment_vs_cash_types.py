from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal, NotRequired, TypeAlias, TypedDict

NumericInput: TypeAlias = Decimal | str | int | float
DateInput: TypeAlias = date | str
OpportunityRateType: TypeAlias = Literal[
    "manual",
    "product_default",
    "inflation_only",
]
RecommendedOption: TypeAlias = Literal["cash", "installment", "equivalent"]
SelectedPaymentOption: TypeAlias = Literal["cash", "installment"]
TransactionStatusValue: TypeAlias = Literal[
    "pending",
    "paid",
    "cancelled",
    "postponed",
    "overdue",
]


class InstallmentVsCashCalculationInput(TypedDict):
    cash_price: NumericInput
    installment_count: int
    inflation_rate_annual: NumericInput
    fees_enabled: bool
    fees_upfront: NumericInput
    first_payment_delay_days: int
    opportunity_rate_type: OpportunityRateType
    installment_amount: NotRequired[NumericInput | None]
    installment_total: NotRequired[NumericInput | None]
    opportunity_rate_annual: NotRequired[NumericInput | None]
    scenario_label: NotRequired[str | None]


class InstallmentVsCashSaveInput(InstallmentVsCashCalculationInput):
    pass


class InstallmentVsCashGoalBridgeInput(TypedDict):
    title: str
    selected_option: SelectedPaymentOption
    current_amount: NumericInput
    priority: int
    description: NotRequired[str | None]
    category: NotRequired[str | None]
    target_date: NotRequired[DateInput | None]


class InstallmentVsCashPlannedExpenseBridgeInput(TypedDict):
    title: str
    selected_option: SelectedPaymentOption
    currency: str
    status: TransactionStatusValue
    description: NotRequired[str | None]
    observation: NotRequired[str | None]
    due_date: NotRequired[DateInput | None]
    first_due_date: NotRequired[DateInput | None]
    upfront_due_date: NotRequired[DateInput | None]
    tag_id: NotRequired[str | None]
    account_id: NotRequired[str | None]
    credit_card_id: NotRequired[str | None]


class InstallmentVsCashIndicatorSnapshot(TypedDict):
    preset_type: str
    source: str
    annual_rate_percent: str
    as_of: str


class InstallmentVsCashComparison(TypedDict):
    cash_option_total: str
    installment_option_total: str
    installment_present_value: str
    installment_real_value_today: str
    present_value_delta_vs_cash: str
    absolute_delta_vs_cash: str
    relative_delta_vs_cash_percent: str
    break_even_discount_percent: str
    break_even_opportunity_rate_annual: str


class InstallmentVsCashCashOption(TypedDict):
    total: str


class InstallmentVsCashInstallmentOption(TypedDict):
    count: int
    amounts: list[str]
    installment_amount: str
    nominal_total: str
    upfront_fees: str
    first_payment_delay_days: int


class InstallmentVsCashOptions(TypedDict):
    cash: InstallmentVsCashCashOption
    installment: InstallmentVsCashInstallmentOption


class InstallmentVsCashNeutralityBand(TypedDict):
    absolute_brl: str
    relative_percent: str


class InstallmentVsCashAssumptions(TypedDict):
    opportunity_rate_type: OpportunityRateType
    opportunity_rate_annual_percent: str
    inflation_rate_annual_percent: str
    periodicity: str
    first_payment_delay_days: int
    upfront_fees_apply_to: str
    neutrality_rule: str


class InstallmentVsCashScheduleItem(TypedDict):
    installment_number: int
    due_in_days: int
    amount: str
    present_value: str
    real_value_today: str
    cumulative_nominal: str
    cumulative_present_value: str
    cumulative_real_value_today: str
    cash_cumulative: str


class InstallmentVsCashResult(TypedDict):
    recommended_option: RecommendedOption
    recommendation_reason: str
    formula_explainer: str
    comparison: InstallmentVsCashComparison
    options: InstallmentVsCashOptions
    neutrality_band: InstallmentVsCashNeutralityBand
    assumptions: InstallmentVsCashAssumptions
    indicator_snapshot: InstallmentVsCashIndicatorSnapshot | None
    schedule: list[InstallmentVsCashScheduleItem]


class InstallmentVsCashNormalizedInput(TypedDict):
    cash_price: str
    installment_count: int
    installment_amount: str
    installment_total: str
    first_payment_delay_days: int
    opportunity_rate_type: OpportunityRateType
    opportunity_rate_annual: str
    inflation_rate_annual: str
    fees_upfront: str
    scenario_label: str | None


@dataclass(frozen=True)
class InstallmentVsCashCalculation:
    tool_id: str
    rule_version: str
    inputs: InstallmentVsCashNormalizedInput
    result: InstallmentVsCashResult


class InstallmentVsCashCalculationResponse(TypedDict):
    tool_id: str
    rule_version: str
    input: InstallmentVsCashNormalizedInput
    result: InstallmentVsCashResult


class SerializedGoal(TypedDict):
    id: str
    title: str
    description: str | None
    category: str | None
    target_amount: str
    current_amount: str
    priority: int
    target_date: str | None
    status: str
    created_at: str | None
    updated_at: str | None


class SerializedTransaction(TypedDict):
    id: str
    title: str
    amount: str
    type: str
    due_date: str
    start_date: str | None
    end_date: str | None
    description: str | None
    observation: str | None
    is_recurring: bool
    is_installment: bool
    installment_count: int | None
    tag_id: str | None
    account_id: str | None
    credit_card_id: str | None
    status: str
    currency: str
    created_at: str | None
    updated_at: str | None


class SerializedSimulation(TypedDict):
    id: str
    user_id: str | None
    tool_id: str
    rule_version: str
    inputs: dict[str, object]
    result: dict[str, object]
    saved: bool
    goal_id: str | None
    created_at: str


class InstallmentVsCashSaveResponse(TypedDict):
    simulation: SerializedSimulation
    calculation: InstallmentVsCashCalculationResponse


class InstallmentVsCashGoalBridgeResponse(TypedDict):
    goal: SerializedGoal
    simulation: SerializedSimulation


class InstallmentVsCashPlannedExpenseBridgeResponse(TypedDict):
    transactions: list[SerializedTransaction]
    simulation: SerializedSimulation
