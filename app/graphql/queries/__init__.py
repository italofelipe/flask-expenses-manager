from __future__ import annotations

import graphene

from .account import AccountQueryMixin
from .budget import BudgetQueryMixin
from .dashboard import DashboardQueryMixin
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
]
