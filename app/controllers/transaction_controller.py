from typing import Any, Dict
from uuid import UUID

import flask
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
from app.utils.pagination import PaginatedResponse

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
            response = jsonify({"error": "Token inválido."})
            response.status_code = 401
            return response

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
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

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

    @doc(description="Deleta (soft delete) uma transação", tags=["Transações"])  # type: ignore
    @jwt_required()  # type: ignore
    def delete(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()

        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": "Token inválido."})
            response.status_code = 401
            return response

        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

        if transaction is None:
            response = jsonify({"error": "Transação não encontrada."})
            response.status_code = 404
            return response

        if str(transaction.user_id) != str(user_id):
            response = jsonify(
                {"error": "Você não tem permissão para deletar esta transação."}
            )
            response.status_code = 403
            return response

        try:
            # Soft delete - marca como deletada
            transaction.deleted = True
            db.session.commit()

            response = jsonify(
                {"message": "Transação deletada com sucesso (soft delete)."}
            )
            response.status_code = 200
            return response

        except Exception as e:
            db.session.rollback()
            response = jsonify(
                {"error": "Erro ao deletar transação", "message": str(e)}
            )
            response.status_code = 500
            return response

    @doc(
        description="Restaura uma transação deletada logicamente",
        tags=["Transações"],
        security=[{"BearerAuth": []}],
    )  # type: ignore
    @jwt_required()  # type: ignore
    def patch(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return jsonify({"error": "Token inválido."}), 401

        user_id = get_jwt_identity()

        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=user_id, deleted=True
        ).first()
        if not transaction:
            response = jsonify({"error": "Transação não encontrada."})
            response.status_code = 404
            return response

        if not transaction.deleted:
            response = jsonify({"error": "Transação não está deletada."})
            response.status_code = 400
            return response

        try:
            transaction.deleted = False
            db.session.commit()
            response = jsonify({"message": "Transação restaurada com sucesso"})
            response.status_code = 200
            return response
        except Exception as e:
            db.session.rollback()
            response = jsonify(
                {"error": "Erro ao restaurar transação", "message": str(e)}
            )
            response.status_code = 500
            return response

    @doc(
        description="Lista todas as transações deletadas (soft deleted) do usuário autenticado",
        tags=["Transações"],
        security=[{"BearerAuth": []}],
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": "Token inválido."})
            response.status_code = 401
            return response

        user_id = get_jwt_identity()

        try:
            transactions = Transaction.query.filter_by(
                user_id=user_id, deleted=True
            ).all()

            serialized = [serialize_transaction(t) for t in transactions]

            response = jsonify({"deleted_transactions": serialized})
            response.status_code = 200
            return response
        except Exception as e:
            db.session.rollback()
            response = jsonify(
                {"error": "Erro ao buscar transações deletadas", "message": str(e)}
            )
            response.status_code = 500
            return response


class TransactionSummaryResource(MethodResource):
    @doc(
        description="Resumo mensal das transações (total de receitas e despesas)",
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "description": "Formato YYYY-MM (ex: 2025-04)",
                "in": "query",
                "type": "string",
            }
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return jsonify({"error": "Token inválido."}), 401

        user_id = get_jwt_identity()
        month = flask.request.args.get("month")
        if not month:
            return (
                jsonify(
                    {"error": "Parâmetro 'month' é obrigatório no formato YYYY-MM."}
                ),
                400,
            )

        try:
            year, month_number = map(int, month.split("-"))
        except ValueError:
            return jsonify({"error": "Formato de mês inválido. Use YYYY-MM."}), 400

        try:
            transactions = (
                Transaction.query.filter_by(user_id=user_id, deleted=False)
                .filter(db.extract("year", Transaction.due_date) == year)
                .filter(db.extract("month", Transaction.due_date) == month_number)
                .all()
            )

            income_total = sum(
                t.amount for t in transactions if t.type == TransactionType.INCOME
            )
            expense_total = sum(
                t.amount for t in transactions if t.type == TransactionType.EXPENSE
            )

            page = int(flask.request.args.get("page", 1))
            page_size = int(flask.request.args.get("page_size", 10))

            serialized = [serialize_transaction(t) for t in transactions]
            response = jsonify(
                {
                    "month": month,
                    "income_total": float(income_total),
                    "expense_total": float(expense_total),
                    **PaginatedResponse.format(
                        serialized, len(transactions), page, page_size
                    ),
                }
            )
            response.status_code = 200
            return response
        except Exception as e:
            db.session.rollback()
            return (
                jsonify({"error": "Erro ao calcular resumo mensal", "message": str(e)}),
                500,
            )


class TransactionForceDeleteResource(MethodResource):
    @doc(
        description="Remove permanentemente uma transação deletada (soft deleted)",
        tags=["Transações"],
        security=[{"BearerAuth": []}],
    )  # type: ignore
    @jwt_required()  # type: ignore
    def delete(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": "Token inválido."})
            response.status_code = 401
            return response

        user_id = get_jwt_identity()

        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=UUID(user_id), deleted=True
        ).first()

        if not transaction:
            response = jsonify(
                {"error": "Transação não encontrada ou não está deletada."}
            )
            response.status_code = 404
            return response

        try:
            db.session.delete(transaction)
            db.session.commit()
            response = jsonify({"message": "Transação removida permanentemente."})
            response.status_code = 200
            return response
        except Exception as e:
            db.session.rollback()
            response = jsonify(
                {"error": "Erro ao deletar permanentemente", "message": str(e)}
            )
            response.status_code = 500
            return response


# Registra a rota
transaction_bp.add_url_rule(
    "", view_func=TransactionResource.as_view("transactionresource")
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transactionupdate"),
    methods=["PUT"],
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transactiondelete"),
    methods=["DELETE"],
)

transaction_bp.add_url_rule(
    "/restore/<uuid:transaction_id>",
    view_func=TransactionResource.as_view("transaction_restore"),
    methods=["PATCH"],
)

transaction_bp.add_url_rule(
    "/deleted",
    view_func=TransactionResource.as_view("transaction_list_deleted"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/<uuid:transaction_id>/force",
    view_func=TransactionForceDeleteResource.as_view("transaction_delete_force"),
    methods=["DELETE"],
)

transaction_bp.add_url_rule(
    "/summary",
    view_func=TransactionSummaryResource.as_view("transaction_monthly_summary"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/list",
    view_func=TransactionResource.as_view("transaction_list_active"),
    methods=["GET"],
)
