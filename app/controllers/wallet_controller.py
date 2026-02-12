"""Wallet controller compatibility facade.

This module preserves legacy imports while routing endpoint registration to the
modular wallet package.
"""

from app.controllers.wallet import register_wallet_dependencies, wallet_bp
from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)
from app.services.investment_service import InvestmentService
from app.services.portfolio_history_service import PortfolioHistoryService
from app.services.portfolio_valuation_service import PortfolioValuationService

__all__ = [
    "wallet_bp",
    "register_wallet_dependencies",
    "InvestmentOperationService",
    "InvestmentOperationError",
    "InvestmentService",
    "PortfolioHistoryService",
    "PortfolioValuationService",
]
