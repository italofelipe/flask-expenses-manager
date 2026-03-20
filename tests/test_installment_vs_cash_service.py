from __future__ import annotations

from decimal import Decimal

from app.services.installment_vs_cash_service import InstallmentVsCashService


def _service() -> InstallmentVsCashService:
    return InstallmentVsCashService(
        default_opportunity_rate_annual_percent=Decimal("12.00")
    )


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "cash_price": "900.00",
        "installment_count": 10,
        "installment_amount": "100.00",
        "first_payment_delay_days": 30,
        "opportunity_rate_type": "manual",
        "opportunity_rate_annual": "12.00",
        "inflation_rate_annual": "4.50",
        "fees_upfront": "0.00",
    }
    payload.update(overrides)
    return payload


def test_installment_vs_cash_service_recommends_cash_when_present_value_is_higher() -> (
    None
):
    result = _service().calculate(_payload())

    assert result.result["recommended_option"] == "cash"
    assert Decimal(result.result["comparison"]["installment_present_value"]) > Decimal(
        result.result["comparison"]["cash_option_total"]
    )


def test_service_recommends_installment_with_high_opportunity_rate() -> None:
    result = _service().calculate(
        _payload(
            cash_price="1000.00",
            opportunity_rate_annual="36.00",
        )
    )

    assert result.result["recommended_option"] == "installment"
    assert Decimal(result.result["comparison"]["installment_present_value"]) < Decimal(
        result.result["comparison"]["cash_option_total"]
    )


def test_installment_vs_cash_service_returns_equivalent_inside_neutrality_band() -> (
    None
):
    result = _service().calculate(
        _payload(
            cash_price="1000.00",
            installment_total="1010.00",
            installment_amount=None,
            installment_count=10,
            opportunity_rate_annual="2.00",
            inflation_rate_annual="2.00",
        )
    )

    assert result.result["recommended_option"] == "equivalent"


def test_installment_vs_cash_service_emits_indicator_snapshot_for_product_default() -> (
    None
):
    result = _service().calculate(
        _payload(
            opportunity_rate_type="product_default",
            opportunity_rate_annual=None,
        )
    )

    assert result.result["indicator_snapshot"] is not None
    assert result.result["indicator_snapshot"]["preset_type"] == "product_default"
