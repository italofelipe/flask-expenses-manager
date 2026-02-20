from __future__ import annotations

import graphene

from .goal import GoalQueryMixin
from .investment import InvestmentQueryMixin
from .transaction import TransactionQueryMixin
from .user import UserQueryMixin
from .wallet import WalletQueryMixin


class Query(
    UserQueryMixin,
    TransactionQueryMixin,
    GoalQueryMixin,
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
    "WalletQueryMixin",
    "InvestmentQueryMixin",
]
