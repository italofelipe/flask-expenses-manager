from typing import Any
from uuid import UUID

from flask import Blueprint, Response, jsonify
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import Schema, fields

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")


class TransactionCreateSchema(Schema):
    title = fields.String(required=True)
    amount = fields.Decimal(required=True, as_string=True)
    type = fields.String(required=True)
    due_date = fields.Date(required=True)
    description = fields.String(required=False)
    observation = fields.String(required=False)
    is_recurring = fields.Boolean(required=False)
    is_installment = fields.Boolean(required=False)
    installment_count = fields.Integer(required=False)
    tag_id = fields.UUID(required=False)
    account_id = fields.UUID(required=False)
    credit_card_id = fields.UUID(required=False)
    status = fields.String(required=False)
    currency = fields.String(required=False)


class TransactionResource(MethodResource):
    @doc(description="Cria uma nova transação", tags=["Transações"])  # type: ignore
    @jwt_required()  # type: ignore
    @use_kwargs(TransactionCreateSchema, location="json")  # type: ignore
    def post(self, **kwargs: Any) -> Response:
        user_id = get_jwt_identity()

        try:
            transaction = Transaction(
                user_id=UUID(user_id),
                title=kwargs["title"],
                amount=kwargs["amount"],
                type=TransactionType(kwargs["type"].lower()),
                due_date=kwargs["due_date"],
                description=kwargs.get("description"),
                observation=kwargs.get("observation"),
                is_recurring=kwargs.get("is_recurring", False),
                is_installment=kwargs.get("is_installment", False),
                installment_count=kwargs.get("installment_count"),
                tag_id=kwargs.get("tag_id"),
                account_id=kwargs.get("account_id"),
                credit_card_id=kwargs.get("credit_card_id"),
                status=TransactionStatus(kwargs.get("status", "pending").lower()),
                currency=kwargs.get("currency", "BRL"),
            )

            db.session.add(transaction)
            db.session.commit()

            created_data = {
                "id": str(transaction.id),
                "title": transaction.title,
                "amount": str(transaction.amount),
                "type": transaction.type.value,
                "due_date": transaction.due_date.isoformat(),
                "description": transaction.description,
                "observation": transaction.observation,
                "is_recurring": transaction.is_recurring,
                "is_installment": transaction.is_installment,
                "installment_count": transaction.installment_count,
                "tag_id": str(transaction.tag_id) if transaction.tag_id else None,
                "account_id": str(transaction.account_id)
                if transaction.account_id
                else None,
                "credit_card_id": str(transaction.credit_card_id)
                if transaction.credit_card_id
                else None,
                "status": transaction.status.value,
                "currency": transaction.currency,
                "created_at": transaction.created_at.isoformat()
                if transaction.created_at
                else None,
                "updated_at": transaction.updated_at.isoformat()
                if transaction.updated_at
                else None,
            }

            response = jsonify(
                {"message": "Transação criada com sucesso", "transaction": created_data}
            )
            response.status_code = 201
            return response

        except Exception as e:
            db.session.rollback()
            response = jsonify({"error": "Erro ao criar transação", "message": str(e)})
            response.status_code = 500
            return response


# Registra a rota
transaction_bp.add_url_rule(
    "", view_func=TransactionResource.as_view("transactionresource")
)
