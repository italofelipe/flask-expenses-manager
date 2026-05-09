"""GraphQL queries for the Accounts domain (#1148)."""

from __future__ import annotations

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import AccountListType, AccountType
from app.models.account import Account


def _to_account_type(a: Account) -> AccountType:
    return AccountType(
        id=str(a.id),
        name=a.name,
        account_type=a.account_type or "checking",
        institution=a.institution,
        initial_balance=a.initial_balance,
    )


class AccountQueryMixin:
    accounts = graphene.Field(AccountListType)
    account = graphene.Field(AccountType, account_id=graphene.UUID(required=True))

    @log_graphql_resolver("accounts")
    def resolve_accounts(self, _info: graphene.ResolveInfo) -> AccountListType:
        user = get_current_user_required()
        rows = Account.query.filter_by(user_id=user.id).order_by(Account.name).all()
        return AccountListType(
            accounts=[_to_account_type(a) for a in rows], total=len(rows)
        )

    @log_graphql_resolver("account")
    def resolve_account(
        self, _info: graphene.ResolveInfo, account_id: object
    ) -> AccountType | None:
        user = get_current_user_required()
        a = Account.query.filter_by(id=account_id, user_id=user.id).first()
        return _to_account_type(a) if a else None
