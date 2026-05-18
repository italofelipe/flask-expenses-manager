from __future__ import annotations

import graphene

from .account import AccountQueryMixin
from .ai_insight import AIInsightQueryMixin
from .budget import BudgetQueryMixin
from .credit_card import CreditCardQueryMixin
from .dashboard import DashboardQueryMixin
from .fiscal import FiscalQueryMixin
from .goal import GoalQueryMixin
from .investment import InvestmentQueryMixin
from .notification import NotificationQueryMixin
from .simulation import SimulationQueryMixin
from .subscription import SubscriptionQueryMixin
from .tag import TagQueryMixin
from .transaction import TransactionQueryMixin
from .user import UserQueryMixin
from .wallet import WalletQueryMixin


class Query(
    UserQueryMixin,
    DashboardQueryMixin,
    TransactionQueryMixin,
    GoalQueryMixin,
    SimulationQueryMixin,
    WalletQueryMixin,
    InvestmentQueryMixin,
    BudgetQueryMixin,
    SubscriptionQueryMixin,
    NotificationQueryMixin,
    TagQueryMixin,
    AccountQueryMixin,
    AIInsightQueryMixin,
    CreditCardQueryMixin,
    FiscalQueryMixin,
    graphene.ObjectType,
):
    pass


__all__ = [
    "Query",
    "UserQueryMixin",
    "DashboardQueryMixin",
    "TransactionQueryMixin",
    "GoalQueryMixin",
    "SimulationQueryMixin",
    "WalletQueryMixin",
    "InvestmentQueryMixin",
    "BudgetQueryMixin",
    "SubscriptionQueryMixin",
    "NotificationQueryMixin",
    "TagQueryMixin",
    "AccountQueryMixin",
    "AIInsightQueryMixin",
    "CreditCardQueryMixin",
    "FiscalQueryMixin",
]
