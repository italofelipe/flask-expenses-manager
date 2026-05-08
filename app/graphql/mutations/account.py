"""GraphQL mutations for the Accounts domain (#1148)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

import graphene

from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import AccountPayload, AccountType
from app.models.account import ACCOUNT_TYPE_VALUES, Account

_ACCOUNT_TYPES = set(ACCOUNT_TYPE_VALUES)


def _to_account_type(a: Account) -> AccountType:
    return AccountType(
        id=str(a.id),
        name=a.name,
        account_type=a.account_type or "checking",
        institution=a.institution,
        initial_balance=a.initial_balance,
    )


class CreateAccountMutation(graphene.Mutation):
    class Arguments:
        name = graphene.String(required=True)
        account_type = graphene.String()
        institution = graphene.String()
        initial_balance = graphene.String()

    Output = AccountPayload

    @log_graphql_resolver("createAccount")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        name: str,
        account_type: str = "checking",
        institution: str | None = None,
        initial_balance: str = "0",
    ) -> AccountPayload:
        user = get_current_user_required()
        name = name.strip()
        if not name:
            raise build_public_graphql_error(
                "name is required", code="VALIDATION_ERROR"
            )
        if len(name) > 100:
            raise build_public_graphql_error(
                "name must be at most 100 characters", code="VALIDATION_ERROR"
            )
        if account_type not in _ACCOUNT_TYPES:
            raise build_public_graphql_error(
                f"account_type must be one of: {', '.join(sorted(_ACCOUNT_TYPES))}",
                code="VALIDATION_ERROR",
            )
        try:
            balance = Decimal(str(initial_balance or "0"))
        except InvalidOperation as exc:
            raise build_public_graphql_error(
                "initial_balance must be a valid decimal", code="VALIDATION_ERROR"
            ) from exc
        account = Account(
            user_id=user.id,
            name=name,
            account_type=account_type,
            institution=institution,
            initial_balance=balance,
        )
        db.session.add(account)
        db.session.commit()
        return AccountPayload(
            ok=True,
            message="Conta criada com sucesso.",
            errors=[],
            data=_to_account_type(account),
        )


class UpdateAccountMutation(graphene.Mutation):
    class Arguments:
        account_id = graphene.UUID(required=True)
        name = graphene.String(required=True)
        account_type = graphene.String()
        institution = graphene.String()
        initial_balance = graphene.String()

    Output = AccountPayload

    @log_graphql_resolver("updateAccount")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        account_id: object,
        name: str,
        account_type: str | None = None,
        institution: str | None = None,
        initial_balance: str | None = None,
    ) -> AccountPayload:
        user = get_current_user_required()
        account = Account.query.filter_by(id=account_id, user_id=user.id).first()
        if not account:
            raise build_public_graphql_error("Account not found", code="NOT_FOUND")
        name = name.strip()
        if not name:
            raise build_public_graphql_error(
                "name is required", code="VALIDATION_ERROR"
            )
        if len(name) > 100:
            raise build_public_graphql_error(
                "name must be at most 100 characters", code="VALIDATION_ERROR"
            )
        if account_type and account_type not in _ACCOUNT_TYPES:
            raise build_public_graphql_error(
                f"account_type must be one of: {', '.join(sorted(_ACCOUNT_TYPES))}",
                code="VALIDATION_ERROR",
            )
        account.name = name
        if account_type:
            account.account_type = account_type
        if institution is not None:
            account.institution = institution or None
        if initial_balance is not None:
            try:
                account.initial_balance = Decimal(str(initial_balance))
            except InvalidOperation as exc:
                raise build_public_graphql_error(
                    "initial_balance must be a valid decimal", code="VALIDATION_ERROR"
                ) from exc
        db.session.commit()
        return AccountPayload(
            ok=True,
            message="Conta atualizada com sucesso.",
            errors=[],
            data=_to_account_type(account),
        )


class DeleteAccountMutation(graphene.Mutation):
    class Arguments:
        account_id = graphene.UUID(required=True)

    Output = AccountPayload

    @log_graphql_resolver("deleteAccount")
    def mutate(self, _info: graphene.ResolveInfo, account_id: object) -> AccountPayload:
        user = get_current_user_required()
        account = Account.query.filter_by(id=account_id, user_id=user.id).first()
        if not account:
            raise build_public_graphql_error("Account not found", code="NOT_FOUND")
        db.session.delete(account)
        db.session.commit()
        return AccountPayload(ok=True, message="Conta removida com sucesso.", errors=[])
