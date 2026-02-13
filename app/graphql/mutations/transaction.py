from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import graphene
from dateutil.relativedelta import relativedelta
from graphql import GraphQLError

from app.controllers.transaction.utils import (
    _build_installment_amounts,
    _validate_recurring_payload,
    serialize_transaction,
)
from app.extensions.database import db
from app.graphql.auth import get_current_user_required
from app.graphql.schema_utils import _parse_optional_date
from app.graphql.types import TransactionTypeObject
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.transaction_reference_authorization_service import (
    TransactionReferenceAuthorizationError,
    enforce_transaction_reference_ownership,
)


class CreateTransactionMutation(graphene.Mutation):
    class Arguments:
        title = graphene.String(required=True)
        amount = graphene.String(required=True)
        type = graphene.String(required=True)
        due_date = graphene.String(required=True)
        description = graphene.String()
        observation = graphene.String()
        is_recurring = graphene.Boolean(default_value=False)
        is_installment = graphene.Boolean(default_value=False)
        installment_count = graphene.Int()
        currency = graphene.String(default_value="BRL")
        status = graphene.String(default_value="pending")
        start_date = graphene.String()
        end_date = graphene.String()
        tag_id = graphene.UUID()
        account_id = graphene.UUID()
        credit_card_id = graphene.UUID()

    items = graphene.List(TransactionTypeObject, required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, **kwargs: Any
    ) -> "CreateTransactionMutation":
        user = get_current_user_required()
        due_date = _parse_optional_date(kwargs.get("due_date"), "due_date")
        if due_date is None:
            raise GraphQLError("Parâmetro 'due_date' é obrigatório.")
        start_date = _parse_optional_date(kwargs.get("start_date"), "start_date")
        end_date = _parse_optional_date(kwargs.get("end_date"), "end_date")
        recurring_error = _validate_recurring_payload(
            is_recurring=bool(kwargs.get("is_recurring", False)),
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
        )
        if recurring_error:
            raise GraphQLError(recurring_error)

        tx_type = str(kwargs["type"]).lower()
        tx_status = str(kwargs.get("status", "pending")).lower()
        amount = Decimal(str(kwargs["amount"]))
        tag_id = kwargs.get("tag_id") or kwargs.get("tagId")
        account_id = kwargs.get("account_id") or kwargs.get("accountId")
        credit_card_id = kwargs.get("credit_card_id") or kwargs.get("creditCardId")
        try:
            enforce_transaction_reference_ownership(
                user_id=UUID(str(user.id)),
                tag_id=tag_id,
                account_id=account_id,
                credit_card_id=credit_card_id,
            )
        except TransactionReferenceAuthorizationError as exc:
            message = (
                str(exc.args[0]) if exc.args else "Referência inválida para transação."
            )
            raise GraphQLError(message) from exc

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            count = int(kwargs["installment_count"])
            if count < 1:
                raise GraphQLError("'installment_count' deve ser maior que zero.")
            group_id = uuid4()
            installment_amounts = _build_installment_amounts(amount, count)
            created: list[Transaction] = []
            for idx in range(count):
                month_due_date = due_date + relativedelta(months=idx)
                created.append(
                    Transaction(
                        user_id=UUID(str(user.id)),
                        title=f"{kwargs['title']} ({idx + 1}/{count})",
                        amount=installment_amounts[idx],
                        type=TransactionType(tx_type),
                        due_date=month_due_date,
                        start_date=start_date,
                        end_date=end_date,
                        description=kwargs.get("description"),
                        observation=kwargs.get("observation"),
                        is_recurring=bool(kwargs.get("is_recurring", False)),
                        is_installment=True,
                        installment_count=count,
                        tag_id=tag_id,
                        account_id=account_id,
                        credit_card_id=credit_card_id,
                        status=TransactionStatus(tx_status),
                        currency=str(kwargs.get("currency", "BRL")),
                        installment_group_id=group_id,
                    )
                )
            db.session.add_all(created)
            db.session.commit()
            return CreateTransactionMutation(
                message="Transações parceladas criadas com sucesso",
                items=[
                    TransactionTypeObject(**serialize_transaction(item))
                    for item in created
                ],
            )

        transaction = Transaction(
            user_id=UUID(str(user.id)),
            title=kwargs["title"],
            amount=amount,
            type=TransactionType(tx_type),
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
            description=kwargs.get("description"),
            observation=kwargs.get("observation"),
            is_recurring=bool(kwargs.get("is_recurring", False)),
            is_installment=bool(kwargs.get("is_installment", False)),
            installment_count=kwargs.get("installment_count"),
            tag_id=tag_id,
            account_id=account_id,
            credit_card_id=credit_card_id,
            status=TransactionStatus(tx_status),
            currency=str(kwargs.get("currency", "BRL")),
        )
        db.session.add(transaction)
        db.session.commit()
        return CreateTransactionMutation(
            message="Transação criada com sucesso",
            items=[TransactionTypeObject(**serialize_transaction(transaction))],
        )


class DeleteTransactionMutation(graphene.Mutation):
    class Arguments:
        transaction_id = graphene.UUID(required=True)

    ok = graphene.Boolean(required=True)
    message = graphene.String(required=True)

    def mutate(
        self, info: graphene.ResolveInfo, transaction_id: UUID
    ) -> "DeleteTransactionMutation":
        user = get_current_user_required()
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()
        if not transaction:
            raise GraphQLError("Transação não encontrada.")
        if str(transaction.user_id) != str(user.id):
            raise GraphQLError("Você não tem permissão para deletar esta transação.")
        transaction.deleted = True
        db.session.commit()
        return DeleteTransactionMutation(
            ok=True, message="Transação deletada com sucesso (soft delete)."
        )
