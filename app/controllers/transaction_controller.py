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

from app.extensions.database import db
from app.extensions.jwt_callbacks import is_token_revoked
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.schemas.transaction_schema import TransactionSchema
from app.utils.pagination import PaginatedResponse

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")

INVALID_TOKEN_MESSAGE = "Token inválido."


def serialize_transaction(transaction: Transaction) -> Dict[str, Any]:
    return {
        "id": str(transaction.id),
        "title": transaction.title,
        "amount": str(transaction.amount),
        "type": transaction.type.value,
        "due_date": transaction.due_date.isoformat(),
        "start_date": transaction.start_date.isoformat()
        if transaction.start_date
        else None,
        "end_date": transaction.end_date.isoformat() if transaction.end_date else None,
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


class TransactionResource(MethodResource):
    @doc(
        description=(
            "Cria uma nova transação.\n\n"
            "Campos obrigatórios: title, amount, type, due_date.\n"
            """Campos opcionais: description, observation,
            is_recurring, is_installment, installment_count,
            currency, status, tag_id, account_id, credit_card_id.\n"""
            "Se is_installment=True, informe installment_count.\n"
            "Se is_recurring=True, informe start_date, end_date.\n\n"
            "Exemplo de request:\n"
            """{ 'title': 'Conta de luz',
            'amount': '150.50', 'type': 'expense',
            'due_date': '2024-02-15',
            'is_installment': True,
            'installment_count': 12,
            'is_recurring': True,
            'start_date': '2024-01-01',
            'end_date': '2024-12-31' }\n\n"""
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação criada com sucesso', 'transaction': [{...}] }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Transação criada com sucesso"},
            400: {"description": "Erro de validação"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    @use_kwargs(TransactionSchema, location="json")  # type: ignore
    def post(self, **kwargs: Any) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
            response.status_code = 401
            return response

        user_id = get_jwt_identity()

        # Bloco para criar transações parceladas se necessário
        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            from decimal import Decimal
            from uuid import uuid4

            from dateutil.relativedelta import relativedelta  # type: ignore

            try:
                group_id = uuid4()
                total = Decimal(kwargs["amount"])
                count = int(kwargs["installment_count"])
                base_date = kwargs["due_date"]
                value = round(total / count, 2)
                title = kwargs["title"]

                transactions = []
                for i in range(count):
                    due = base_date + relativedelta(months=i)
                    t = Transaction(
                        user_id=UUID(user_id),
                        title=f"{title} ({i+1}/{count})",
                        amount=value,
                        type=TransactionType(kwargs["type"].lower()),
                        due_date=due,
                        start_date=kwargs.get("start_date"),
                        end_date=kwargs.get("end_date"),
                        description=kwargs.get("description"),
                        observation=kwargs.get("observation"),
                        is_recurring=kwargs.get("is_recurring", False),
                        is_installment=True,
                        installment_count=count,
                        tag_id=kwargs.get("tag_id"),
                        account_id=kwargs.get("account_id"),
                        credit_card_id=kwargs.get("credit_card_id"),
                        status=TransactionStatus(
                            kwargs.get("status", "pending").lower()
                        ),
                        currency=kwargs.get("currency", "BRL"),
                        installment_group_id=group_id,
                    )
                    transactions.append(t)

                db.session.add_all(transactions)
                db.session.commit()

                created_data = [serialize_transaction(t) for t in transactions]
                return (
                    jsonify(
                        {
                            "message": "Transações parceladas criadas com sucesso",
                            "transactions": created_data,
                        }
                    ),
                    201,
                )
            except Exception as e:
                db.session.rollback()
                return (
                    jsonify(
                        {
                            "error": "Erro ao criar transações parceladas",
                            "message": str(e),
                        }
                    ),
                    500,
                )
        else:
            try:
                transaction = Transaction(
                    user_id=UUID(user_id),
                    title=kwargs["title"],
                    amount=kwargs["amount"],
                    type=TransactionType(kwargs["type"].lower()),
                    due_date=kwargs["due_date"],
                    start_date=kwargs.get("start_date"),
                    end_date=kwargs.get("end_date"),
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

                created_data = [serialize_transaction(transaction)]

                response = jsonify(
                    {
                        "message": "Transação criada com sucesso",
                        "transaction": created_data,
                    }
                )
                response.status_code = 201
                return response

            except Exception as e:
                db.session.rollback()
                response = jsonify(
                    {"error": "Erro ao criar transação", "message": str(e)}
                )
                response.status_code = 500
                return response

    @doc(
        description=(
            "Atualiza dados de uma transação existente.\n\n"
            "Campos aceitos: qualquer campo da transação.\n"
            "Se status=PAID, é obrigatório informar paid_at.\n\n"
            "Exemplo de request:\n"
            "{ 'status': 'paid', 'paid_at': '2024-02-20T10:00:00Z' }\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação atualizada com sucesso', 'transaction': {...} }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Transação atualizada com sucesso"},
            400: {"description": "Erro de validação"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Transação não encontrada"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    @use_kwargs(TransactionSchema(partial=True), location="json")  # type: ignore
    def put(self, transaction_id: UUID, **kwargs: Any):
        verify_jwt_in_request()
        jwt_data = get_jwt()

        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
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

        # Validações de status e paid_at
        from datetime import datetime

        # Validação: status=PAID exige paid_at
        if kwargs.get("status", "").lower() == "paid" and not kwargs.get("paid_at"):
            return (
                jsonify(
                    {
                        "error": (
                            "É obrigatório informar 'paid_at' ao marcar a transação "
                            "como paga (status=PAID)."
                        )
                    }
                ),
                400,
            )

        # Validação: paid_at exige status=PAID
        if kwargs.get("paid_at") and kwargs.get("status", "").lower() != "paid":
            return (
                jsonify(
                    {"error": "'paid_at' só pode ser definido se o status for 'PAID'."}
                ),
                400,
            )

        # Validação: paid_at não pode estar no futuro
        if "paid_at" in kwargs and kwargs["paid_at"] is not None:
            if kwargs["paid_at"] > datetime.utcnow():
                return (
                    jsonify({"error": "'paid_at' não pode ser uma data futura."}),
                    400,
                )

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

    @doc(
        description=(
            "Deleta (soft delete) uma transação.\n\n"
            "A transação não é removida do banco, apenas marcada como deletada.\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação deletada com sucesso (soft delete).' }"
        ),
        params={
            "transaction_id": {"description": "ID da transação", "type": "string"},
        },
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Transação deletada com sucesso"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Transação não encontrada"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def delete(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()

        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
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
        description=(
            "Restaura uma transação deletada logicamente.\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação restaurada com sucesso' }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Transação restaurada com sucesso"},
            400: {"description": "Transação não está deletada"},
            401: {"description": "Token inválido"},
            404: {"description": "Transação não encontrada"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def patch(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return jsonify({"error": INVALID_TOKEN_MESSAGE}), 401

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
        description=(
            "Lista todas as transações deletadas (soft deleted) do usuário autenticado.\n\n"
            "Exemplo de resposta:\n"
            "{ 'deleted_transactions': [{...}] }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Lista de transações deletadas"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get_deleted(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
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

    @doc(
        description=(
            "Lista todas as transações ativas do usuário autenticado.\n\n"
            "Filtros disponíveis:\n"
            "- page: número da página\n"
            "- per_page: itens por página\n"
            "- type: tipo da transação (income, expense)\n"
            "- status: status da transação\n"
            "- start_date, end_date: período (YYYY-MM-DD)\n"
            "- tag_id, account_id, credit_card_id: filtros por relacionamento\n\n"
            "Exemplo de resposta:\n"
            "{ 'transactions': [...], 'total': 20, 'page': 1, 'per_page': 10 }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "page": {"description": "Número da página", "type": "integer"},
            "per_page": {"description": "Itens por página", "type": "integer"},
            "type": {
                "description": "Tipo da transação (income, expense)",
                "type": "string",
            },
            "status": {"description": "Status da transação", "type": "string"},
            "start_date": {
                "description": "Data inicial (YYYY-MM-DD)",
                "type": "string",
            },
            "end_date": {"description": "Data final (YYYY-MM-DD)", "type": "string"},
            "tag_id": {"description": "Filtrar por tag", "type": "string"},
            "account_id": {"description": "Filtrar por conta", "type": "string"},
            "credit_card_id": {
                "description": "Filtrar por cartão de crédito",
                "type": "string",
            },
        },
        responses={
            200: {"description": "Lista de transações"},
            401: {"description": "Token inválido ou expirado"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get_active(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
            response.status_code = 401
            return response

        user_id = get_jwt_identity()

        try:
            transactions = Transaction.query.filter_by(
                user_id=user_id, deleted=False
            ).all()

            serialized = [serialize_transaction(t) for t in transactions]

            response = jsonify(
                {
                    "transactions": serialized,
                    "total": len(transactions),
                    "page": 1,
                    "per_page": len(transactions),
                }
            )
            response.status_code = 200
            return response
        except Exception as e:
            db.session.rollback()
            response = jsonify(
                {"error": "Erro ao buscar transações ativas", "message": str(e)}
            )
            response.status_code = 500
            return response


class TransactionSummaryResource(MethodResource):
    @doc(
        description=(
            "Resumo mensal das transações (total de receitas e despesas).\n\n"
            "Parâmetro obrigatório: month=YYYY-MM.\n\n"
            "Exemplo de resposta:\n"
            "{ 'month': '2024-02', 'income_total': 5000.00, 'expense_total': 3000.00, ... }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "description": "Formato YYYY-MM (ex: 2025-04)",
                "in": "query",
                "type": "string",
            },
        },
        responses={
            200: {"description": "Resumo mensal de transações"},
            400: {"description": "Parâmetro inválido"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return jsonify({"error": INVALID_TOKEN_MESSAGE}), 401

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
        description=(
            "Remove permanentemente uma transação deletada (soft deleted).\n\n"
            "Só pode ser usada em transações já marcadas como deletadas.\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação removida permanentemente.' }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "transaction_id": {
                "description": "ID da transação a ser removida",
                "type": "string",
            },
        },
        responses={
            200: {"description": "Transação removida permanentemente"},
            401: {"description": "Token inválido"},
            404: {"description": "Transação não encontrada ou não está deletada"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def delete(self, transaction_id: UUID) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            response = jsonify({"error": INVALID_TOKEN_MESSAGE})
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
