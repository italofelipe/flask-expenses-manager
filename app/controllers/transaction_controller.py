from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, Response, jsonify
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)
from marshmallow import Schema, fields

from app.extensions.database import db
from app.extensions.jwt_callbacks import is_token_revoked
from app.models.transaction import Transaction, TransactionStatus, TransactionType

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")


def serialize_transaction(transaction: Transaction) -> Dict[str, Any]:
    return {
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
        "account_id": str(transaction.account_id) if transaction.account_id else None,
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


class TransactionUpdateSchema(Schema):
    title = fields.String(required=False)
    amount = fields.Decimal(required=False, as_string=True)
    type = fields.String(required=False)
    due_date = fields.Date(required=False)
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
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return jsonify({"error": "Token inválido."}), 401

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

            created_data = serialize_transaction(transaction)

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

    @doc(description="Atualiza dados de uma transação", tags=["Transações"])  # type: ignore
    @jwt_required()  # type: ignore
    @use_kwargs(TransactionUpdateSchema, location="json")  # type: ignore
    def put(self, transaction_id: UUID, **kwargs: Any):
        verify_jwt_in_request()
        jwt_data = get_jwt()

        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": "Token inválido."})
            response.status_code = 401
            return response
        user_id = get_jwt_identity()
        transaction = Transaction.query.get(transaction_id)

        if transaction is None:
            response = jsonify({"error": "Transação não encontrada."})
            response.status_code = 404
            return response

        if str(transaction.user_id) != str(user_id):
            response = jsonify(
                {"error": "Você não tem permissão para editar esta transação."}
            )
            response.status_code = 403
            return response

        try:
            for field, value in kwargs.items():
                if hasattr(transaction, field):
                    setattr(transaction, field, value)

            db.session.commit()

            updated_data = serialize_transaction(transaction)

            response = jsonify(
                {
                    "message": "Transação atualizada com sucesso",
                    "transaction": updated_data,
                }
            )
            response.status_code = 200
            return response

        except Exception as e:
            db.session.rollback()
            return (
                jsonify({"error": "Erro ao atualizar transação", "message": str(e)}),
                500,
            )


# Registra a rota
transaction_bp.add_url_rule(
    "", view_func=TransactionResource.as_view("transactionresource")
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transactionupdate"),
    methods=["PUT"],
)
