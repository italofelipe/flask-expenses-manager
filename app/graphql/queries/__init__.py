from __future__ import annotations

import graphene

from .goal import GoalQueryMixin
from .investment import InvestmentQueryMixin
from .simulation import SimulationQueryMixin
from .transaction import TransactionQueryMixin
from .user import UserQueryMixin
from .wallet import WalletQueryMixin


class Query(
    UserQueryMixin,
    TransactionQueryMixin,
    GoalQueryMixin,
    SimulationQueryMixin,
    WalletQueryMixin,
    InvestmentQueryMixin,
    graphene.ObjectType,
):
    pass


__all__ = [
    "Query",
    "UserQueryMixin",
    "TransactionQueryMixin",
    "GoalQueryMixin",
    "SimulationQueryMixin",
    "WalletQueryMixin",
    "InvestmentQueryMixin",
]
