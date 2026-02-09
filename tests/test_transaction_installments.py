from decimal import Decimal

import pytest

from app.controllers.transaction_controller import _build_installment_amounts


def test_build_installment_amounts_preserves_total() -> None:
    total = Decimal("100.00")
    amounts = _build_installment_amounts(total, 3)

    assert amounts == [Decimal("33.33"), Decimal("33.33"), Decimal("33.34")]
    assert sum(amounts) == total


def test_build_installment_amounts_with_exact_division() -> None:
    total = Decimal("120.00")
    amounts = _build_installment_amounts(total, 3)

    assert amounts == [Decimal("40.00"), Decimal("40.00"), Decimal("40.00")]
    assert sum(amounts) == total


def test_build_installment_amounts_invalid_count() -> None:
    with pytest.raises(ValueError):
        _build_installment_amounts(Decimal("10.00"), 0)
