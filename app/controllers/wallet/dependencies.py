from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from flask import Flask, current_app

from app.application.services.investment_application_service import (
    InvestmentApplicationService,
)
from app.application.services.wallet_application_service import WalletApplicationService
from app.services.investment_operation_service import InvestmentOperationService
from app.services.investment_service import InvestmentService
from app.services.portfolio_history_service import PortfolioHistoryService
from app.services.portfolio_valuation_service import PortfolioValuationService

WALLET_DEPENDENCIES_EXTENSION_KEY = "wallet_dependencies"


@dataclass(frozen=True)
class WalletDependencies:
    wallet_application_service_factory: Callable[[UUID], WalletApplicationService]
    investment_application_service_factory: Callable[
        [UUID], InvestmentApplicationService
    ]
    investment_operation_service_factory: Callable[[UUID], InvestmentOperationService]
    portfolio_history_service_factory: Callable[[UUID], PortfolioHistoryService]
    portfolio_valuation_service_factory: Callable[[UUID], PortfolioValuationService]
    calculate_estimated_value: Callable[[dict[str, Any]], Any]
    get_market_price: Callable[[str | None], Any]


def _default_dependencies() -> WalletDependencies:
    return WalletDependencies(
        wallet_application_service_factory=WalletApplicationService.with_defaults,
        investment_application_service_factory=(
            InvestmentApplicationService.with_defaults
        ),
        investment_operation_service_factory=InvestmentOperationService,
        portfolio_history_service_factory=PortfolioHistoryService,
        portfolio_valuation_service_factory=PortfolioValuationService,
        calculate_estimated_value=InvestmentService.calculate_estimated_value,
        get_market_price=lambda ticker: InvestmentService.get_market_price(
            ticker or ""
        ),
    )


def register_wallet_dependencies(
    app: Flask,
    dependencies: WalletDependencies | None = None,
) -> None:
    if dependencies is None:
        dependencies = _default_dependencies()
    app.extensions.setdefault(WALLET_DEPENDENCIES_EXTENSION_KEY, dependencies)


def get_wallet_dependencies() -> WalletDependencies:
    configured = current_app.extensions.get(WALLET_DEPENDENCIES_EXTENSION_KEY)
    if isinstance(configured, WalletDependencies):
        return configured
    fallback = _default_dependencies()
    current_app.extensions[WALLET_DEPENDENCIES_EXTENSION_KEY] = fallback
    return fallback
