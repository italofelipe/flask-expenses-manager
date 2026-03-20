from __future__ import annotations

from datetime import date
from decimal import ROUND_DOWN, Decimal
from math import isclose, pow

from app.services.installment_vs_cash_types import (
    InstallmentVsCashCalculation,
    InstallmentVsCashCalculationInput,
    InstallmentVsCashIndicatorSnapshot,
    InstallmentVsCashResult,
    InstallmentVsCashScheduleItem,
    NumericInput,
    OpportunityRateType,
    RecommendedOption,
)


class InstallmentVsCashService:
    TOOL_ID = "installment_vs_cash"
    RULE_VERSION = "2026.1"
    NEUTRALITY_ABSOLUTE_BRL = Decimal("50.00")
    NEUTRALITY_PERCENT = Decimal("0.02")

    def __init__(self, *, default_opportunity_rate_annual_percent: Decimal) -> None:
        self._default_opportunity_rate_annual_percent = (
            default_opportunity_rate_annual_percent
        )

    def calculate(
        self,
        payload: InstallmentVsCashCalculationInput,
    ) -> InstallmentVsCashCalculation:
        cash_price = _to_money(payload["cash_price"])
        installment_count = int(payload["installment_count"])
        installment_amounts = _resolve_installment_amounts(
            installment_amount=payload.get("installment_amount"),
            installment_total=payload.get("installment_total"),
            installment_count=installment_count,
        )
        installment_nominal_total = _sum_money(installment_amounts)
        fees_upfront = _to_money(payload.get("fees_upfront", "0.00"))
        first_payment_delay_days = int(payload.get("first_payment_delay_days", 30))
        opportunity_rate_type = str(payload.get("opportunity_rate_type", "manual"))
        inflation_rate_annual_percent = Decimal(str(payload["inflation_rate_annual"]))
        opportunity_rate_annual_percent, indicator_snapshot = (
            self._resolve_opportunity_rate(
                opportunity_rate_type=opportunity_rate_type,
                opportunity_rate_annual_percent=payload.get("opportunity_rate_annual"),
                inflation_rate_annual_percent=inflation_rate_annual_percent,
            )
        )

        opportunity_rate_monthly = _effective_monthly_rate(
            opportunity_rate_annual_percent
        )
        inflation_rate_monthly = _effective_monthly_rate(inflation_rate_annual_percent)
        schedule = self._build_schedule(
            installment_amounts=installment_amounts,
            first_payment_delay_days=first_payment_delay_days,
            opportunity_rate_monthly=opportunity_rate_monthly,
            inflation_rate_monthly=inflation_rate_monthly,
            cash_total=cash_price,
        )
        installment_present_value = _sum_money(
            [fees_upfront, *[Decimal(item["present_value"]) for item in schedule]]
        )
        installment_real_value_today = _sum_money(
            [fees_upfront, *[Decimal(item["real_value_today"]) for item in schedule]]
        )
        installment_option_total = _to_money(installment_nominal_total + fees_upfront)
        cash_option_total = cash_price

        delta_vs_cash = _to_money(installment_present_value - cash_option_total)
        absolute_delta = abs(delta_vs_cash)
        relative_delta = (
            (absolute_delta / cash_option_total)
            if cash_option_total > Decimal("0")
            else Decimal("0")
        )
        recommended_option = self._resolve_recommendation(
            delta_vs_cash=delta_vs_cash,
            absolute_delta=absolute_delta,
            relative_delta=relative_delta,
        )

        result: InstallmentVsCashResult = {
            "recommended_option": recommended_option,
            "recommendation_reason": self._build_recommendation_reason(
                recommended_option=recommended_option,
                delta_vs_cash=delta_vs_cash,
            ),
            "formula_explainer": self._build_formula_explainer(
                opportunity_rate_type=opportunity_rate_type,
                opportunity_rate_annual_percent=opportunity_rate_annual_percent,
                inflation_rate_annual_percent=inflation_rate_annual_percent,
                first_payment_delay_days=first_payment_delay_days,
            ),
            "comparison": {
                "cash_option_total": _money_str(cash_option_total),
                "installment_option_total": _money_str(installment_option_total),
                "installment_present_value": _money_str(installment_present_value),
                "installment_real_value_today": _money_str(
                    installment_real_value_today
                ),
                "present_value_delta_vs_cash": _money_str(delta_vs_cash),
                "absolute_delta_vs_cash": _money_str(absolute_delta),
                "relative_delta_vs_cash_percent": _percent_str(relative_delta * 100),
                "break_even_discount_percent": _percent_str(
                    self._break_even_discount_percent(
                        cash_price=cash_option_total,
                        installment_present_value=installment_present_value,
                    )
                ),
                "break_even_opportunity_rate_annual": _percent_str(
                    self._break_even_opportunity_rate_annual(
                        cash_price=cash_option_total,
                        installment_amounts=installment_amounts,
                        fees_upfront=fees_upfront,
                        first_payment_delay_days=first_payment_delay_days,
                    )
                ),
            },
            "options": {
                "cash": {
                    "total": _money_str(cash_option_total),
                },
                "installment": {
                    "count": installment_count,
                    "amounts": [_money_str(item) for item in installment_amounts],
                    "installment_amount": _money_str(installment_amounts[0]),
                    "nominal_total": _money_str(installment_nominal_total),
                    "upfront_fees": _money_str(fees_upfront),
                    "first_payment_delay_days": first_payment_delay_days,
                },
            },
            "neutrality_band": {
                "absolute_brl": _money_str(self.NEUTRALITY_ABSOLUTE_BRL),
                "relative_percent": _percent_str(self.NEUTRALITY_PERCENT * 100),
            },
            "assumptions": {
                "opportunity_rate_type": opportunity_rate_type,
                "opportunity_rate_annual_percent": _percent_str(
                    opportunity_rate_annual_percent
                ),
                "inflation_rate_annual_percent": _percent_str(
                    inflation_rate_annual_percent
                ),
                "periodicity": "monthly",
                "first_payment_delay_days": first_payment_delay_days,
                "upfront_fees_apply_to": "installment_option",
                "neutrality_rule": (
                    "equivalent quando a diferenca absoluta ficar abaixo de R$ 50,00 "
                    "e a diferenca relativa ficar abaixo de 2% do preco a vista."
                ),
            },
            "indicator_snapshot": indicator_snapshot,
            "schedule": schedule,
        }
        inputs = {
            "cash_price": _money_str(cash_price),
            "installment_count": installment_count,
            "installment_amount": _money_str(installment_amounts[0]),
            "installment_total": _money_str(installment_nominal_total),
            "first_payment_delay_days": first_payment_delay_days,
            "opportunity_rate_type": opportunity_rate_type,
            "opportunity_rate_annual": _percent_str(opportunity_rate_annual_percent),
            "inflation_rate_annual": _percent_str(inflation_rate_annual_percent),
            "fees_upfront": _money_str(fees_upfront),
            "scenario_label": payload.get("scenario_label"),
        }

        return InstallmentVsCashCalculation(
            tool_id=self.TOOL_ID,
            rule_version=self.RULE_VERSION,
            inputs=inputs,
            result=result,
        )

    def _build_schedule(
        self,
        *,
        installment_amounts: list[Decimal],
        first_payment_delay_days: int,
        opportunity_rate_monthly: float,
        inflation_rate_monthly: float,
        cash_total: Decimal,
    ) -> list[InstallmentVsCashScheduleItem]:
        schedule: list[InstallmentVsCashScheduleItem] = []
        cumulative_nominal = Decimal("0.00")
        cumulative_present = Decimal("0.00")
        cumulative_real = Decimal("0.00")
        for index, installment_amount in enumerate(installment_amounts, start=1):
            due_in_days = first_payment_delay_days + (index - 1) * 30
            period = Decimal(due_in_days) / Decimal("30")
            present_value = _to_money(
                Decimal(
                    installment_amount
                    / Decimal(pow(1 + opportunity_rate_monthly, float(period)))
                )
            )
            real_value = _to_money(
                Decimal(
                    installment_amount
                    / Decimal(pow(1 + inflation_rate_monthly, float(period)))
                )
            )
            cumulative_nominal = _to_money(cumulative_nominal + installment_amount)
            cumulative_present = _to_money(cumulative_present + present_value)
            cumulative_real = _to_money(cumulative_real + real_value)
            schedule.append(
                {
                    "installment_number": index,
                    "due_in_days": due_in_days,
                    "amount": _money_str(installment_amount),
                    "present_value": _money_str(present_value),
                    "real_value_today": _money_str(real_value),
                    "cumulative_nominal": _money_str(cumulative_nominal),
                    "cumulative_present_value": _money_str(cumulative_present),
                    "cumulative_real_value_today": _money_str(cumulative_real),
                    "cash_cumulative": _money_str(cash_total),
                }
            )
        return schedule

    def _resolve_opportunity_rate(
        self,
        *,
        opportunity_rate_type: OpportunityRateType,
        opportunity_rate_annual_percent: NumericInput | None,
        inflation_rate_annual_percent: Decimal,
    ) -> tuple[Decimal, InstallmentVsCashIndicatorSnapshot | None]:
        if opportunity_rate_type == "manual":
            return Decimal(str(opportunity_rate_annual_percent)), None
        if opportunity_rate_type == "inflation_only":
            return inflation_rate_annual_percent, {
                "preset_type": "inflation_only",
                "source": "request.inflation_rate_annual",
                "annual_rate_percent": _percent_str(inflation_rate_annual_percent),
                "as_of": date.today().isoformat(),
            }
        return self._default_opportunity_rate_annual_percent, {
            "preset_type": "product_default",
            "source": "auraxis_product_config",
            "annual_rate_percent": _percent_str(
                self._default_opportunity_rate_annual_percent
            ),
            "as_of": date.today().isoformat(),
        }

    def _resolve_recommendation(
        self,
        *,
        delta_vs_cash: Decimal,
        absolute_delta: Decimal,
        relative_delta: Decimal,
    ) -> RecommendedOption:
        if (
            absolute_delta < self.NEUTRALITY_ABSOLUTE_BRL
            and relative_delta < self.NEUTRALITY_PERCENT
        ):
            return "equivalent"
        if delta_vs_cash < Decimal("0"):
            return "installment"
        return "cash"

    def _build_recommendation_reason(
        self,
        *,
        recommended_option: str,
        delta_vs_cash: Decimal,
    ) -> str:
        if recommended_option == "equivalent":
            return (
                "A diferença ficou dentro da banda de neutralidade, então as duas "
                "opções são equivalentes nas premissas informadas."
            )
        amount = _money_str(abs(delta_vs_cash))
        if recommended_option == "installment":
            return (
                f"O parcelado ficou {amount} abaixo do pagamento à vista em valor "
                "presente nas premissas informadas."
            )
        return (
            f"O pagamento à vista preserva {amount} a mais do que o parcelado em "
            "valor presente nas premissas informadas."
        )

    def _build_formula_explainer(
        self,
        *,
        opportunity_rate_type: str,
        opportunity_rate_annual_percent: Decimal,
        inflation_rate_annual_percent: Decimal,
        first_payment_delay_days: int,
    ) -> str:
        return (
            "Comparação feita por valor presente do parcelado contra o preço à vista, "
            f"com taxa de oportunidade {opportunity_rate_type} em "
            f"{_percent_str(opportunity_rate_annual_percent)} a.a., inflação em "
            f"{_percent_str(inflation_rate_annual_percent)} a.a. e primeira parcela "
            f"em {first_payment_delay_days} dia(s)."
        )

    def _break_even_discount_percent(
        self,
        *,
        cash_price: Decimal,
        installment_present_value: Decimal,
    ) -> Decimal:
        if cash_price <= Decimal("0"):
            return Decimal("0.00")
        discount = ((cash_price - installment_present_value) / cash_price) * 100
        return _to_percent(max(discount, Decimal("0")))

    def _break_even_opportunity_rate_annual(
        self,
        *,
        cash_price: Decimal,
        installment_amounts: list[Decimal],
        fees_upfront: Decimal,
        first_payment_delay_days: int,
    ) -> Decimal:
        low = 0.0
        high = 100.0
        target = float(cash_price)
        for _ in range(40):
            mid = (low + high) / 2
            monthly_rate = _effective_monthly_rate(Decimal(str(mid)))
            candidate = float(fees_upfront)
            for index, installment_amount in enumerate(installment_amounts, start=1):
                due_in_days = first_payment_delay_days + (index - 1) * 30
                period = due_in_days / 30
                candidate += float(installment_amount) / pow(1 + monthly_rate, period)
            if isclose(candidate, target, rel_tol=1e-6, abs_tol=1e-6):
                return _to_percent(Decimal(str(mid)))
            if candidate > target:
                low = mid
            else:
                high = mid
        return _to_percent(Decimal(str((low + high) / 2)))


def _resolve_installment_amounts(
    *,
    installment_amount: NumericInput | None,
    installment_total: NumericInput | None,
    installment_count: int,
) -> list[Decimal]:
    if installment_amount is not None:
        amount = _to_money(installment_amount)
        amounts = [amount for _ in range(installment_count)]
        if installment_total is not None:
            expected = _to_money(installment_total)
            actual = _sum_money(amounts)
            if abs(expected - actual) > Decimal("0.05"):
                raise ValueError(
                    "installment_total difere do valor implícito por "
                    "installment_amount."
                )
        return amounts
    total = _to_money(installment_total)
    base_amount = (total / installment_count).quantize(
        Decimal("0.01"), rounding=ROUND_DOWN
    )
    amounts = [base_amount] * installment_count
    remainder = _to_money(total - _sum_money(amounts))
    amounts[-1] = _to_money(amounts[-1] + remainder)
    return amounts


def _effective_monthly_rate(annual_percent: Decimal) -> float:
    annual_decimal = float(annual_percent) / 100
    return pow(1 + annual_decimal, 1 / 12) - 1


def _to_money(value: NumericInput) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _to_percent(value: Decimal) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _money_str(value: Decimal) -> str:
    return format(_to_money(value), ".2f")


def _percent_str(value: Decimal) -> str:
    return format(_to_percent(value), ".2f")


def _sum_money(values: list[Decimal]) -> Decimal:
    total = Decimal("0.00")
    for value in values:
        total += _to_money(value)
    return _to_money(total)
