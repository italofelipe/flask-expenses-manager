# mypy: disable-error-code=no-any-return

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import Blueprint, Response, request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import (
    get_jwt,
    get_jwt_identity,
    jwt_required,
    verify_jwt_in_request,
)

from app.controllers.transaction_controller_utils import (
    CONTRACT_HEADER,
    _apply_transaction_updates,
    _build_installment_amounts,
    _compat_error,
    _compat_success,
    _enforce_transaction_reference_ownership_or_error,
    _internal_error_response,
    _invalid_token_response,
    _parse_month_param,
    _parse_optional_date,
    _parse_optional_uuid,
    _parse_positive_int,
    _resolve_transaction_ordering,
    _validate_recurring_payload,
    serialize_transaction,
)
from app.extensions.database import db
from app.extensions.jwt_callbacks import is_token_revoked
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.schemas.transaction_schema import TransactionSchema
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.utils.pagination import PaginatedResponse

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")


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
            'amount': '150.50',
            'type': 'expense',
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
        params={
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            201: {"description": "Transação criada com sucesso"},
            400: {"description": "Erro de validação"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    @use_kwargs(TransactionSchema, location="json")  # type: ignore
    def post(self, **kwargs: Any) -> Response:  # noqa: C901
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].lower()

        recurring_error = _validate_recurring_payload(
            is_recurring=bool(kwargs.get("is_recurring", False)),
            due_date=kwargs.get("due_date"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        )
        if recurring_error:
            return _compat_error(
                legacy_payload={"error": recurring_error},
                status_code=400,
                message=recurring_error,
                error_code="VALIDATION_ERROR",
            )

        reference_error = _enforce_transaction_reference_ownership_or_error(
            user_id=user_uuid,
            tag_id=kwargs.get("tag_id"),
            account_id=kwargs.get("account_id"),
            credit_card_id=kwargs.get("credit_card_id"),
        )
        if reference_error:
            return _compat_error(
                legacy_payload={"error": reference_error},
                status_code=400,
                message=reference_error,
                error_code="VALIDATION_ERROR",
            )

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            from uuid import uuid4

            from dateutil.relativedelta import relativedelta

            try:
                group_id = uuid4()
                total = Decimal(kwargs["amount"])
                count = int(kwargs["installment_count"])
                base_date = kwargs["due_date"]
                installment_amounts = _build_installment_amounts(total, count)
                title = kwargs["title"]
                if "type" in kwargs:
                    kwargs["type"] = kwargs["type"].lower()

                transactions = []
                for i in range(count):
                    due = base_date + relativedelta(months=i)
                    transaction = Transaction(
                        user_id=user_uuid,
                        title=f"{title} ({i + 1}/{count})",
                        amount=installment_amounts[i],
                        type=TransactionType(kwargs["type"]),
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
                    transactions.append(transaction)

                db.session.add_all(transactions)
                db.session.commit()

                created_data = [serialize_transaction(item) for item in transactions]
                return _compat_success(
                    legacy_payload={
                        "message": "Transações parceladas criadas com sucesso",
                        "transactions": created_data,
                    },
                    status_code=201,
                    message="Transações parceladas criadas com sucesso",
                    data={"transactions": created_data},
                )
            except Exception:
                db.session.rollback()
                return _internal_error_response(
                    message="Erro ao criar transações parceladas",
                    log_context="transaction.installment.create_failed",
                )

        try:
            transaction = Transaction(
                user_id=user_uuid,
                title=kwargs["title"],
                amount=kwargs["amount"],
                type=TransactionType(kwargs["type"]),
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

            return _compat_success(
                legacy_payload={
                    "message": "Transação criada com sucesso",
                    "transaction": created_data,
                },
                status_code=201,
                message="Transação criada com sucesso",
                data={"transaction": created_data},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao criar transação",
                log_context="transaction.create_failed",
            )

    @doc(
        description=(
            "Atualiza dados de uma transação existente.\n\n"
            "Campos aceitos: title, description, observation, is_recurring, "
            "is_installment, installment_count, amount, currency, status, type, "
            "due_date, start_date, end_date, tag_id, account_id, credit_card_id, "
            "paid_at.\n"
            "Se status=PAID, é obrigatório informar paid_at.\n\n"
            "Exemplo de request:\n"
            "{ 'status': 'paid', 'paid_at': '2024-02-20T10:00:00Z' }\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação atualizada com sucesso', 'transaction': {...} }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "transaction_id": {"description": "ID da transação", "type": "string"},
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
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
    def put(self, transaction_id: UUID, **kwargs: Any) -> Response:  # noqa: C901
        verify_jwt_in_request()
        jwt_data = get_jwt()

        if is_token_revoked(jwt_data["jti"]):
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

        if transaction is None:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        if str(transaction.user_id) != str(user_id):
            return _compat_error(
                legacy_payload={
                    "error": "Você não tem permissão para editar esta transação."
                },
                status_code=403,
                message="Você não tem permissão para editar esta transação.",
                error_code="FORBIDDEN",
            )

        if kwargs.get("type") is not None:
            kwargs["type"] = str(kwargs["type"]).lower()
        if kwargs.get("status") is not None:
            kwargs["status"] = str(kwargs["status"]).lower()

        if kwargs.get("status", "").lower() == "paid" and not kwargs.get("paid_at"):
            return _compat_error(
                legacy_payload={
                    "error": (
                        "É obrigatório informar 'paid_at' ao marcar a transação "
                        "como paga (status=PAID)."
                    )
                },
                status_code=400,
                message=(
                    "É obrigatório informar 'paid_at' ao marcar a transação "
                    "como paga (status=PAID)."
                ),
                error_code="VALIDATION_ERROR",
            )

        if kwargs.get("paid_at") and kwargs.get("status", "").lower() != "paid":
            return _compat_error(
                legacy_payload={
                    "error": "'paid_at' só pode ser definido se o status for 'PAID'."
                },
                status_code=400,
                message="'paid_at' só pode ser definido se o status for 'PAID'.",
                error_code="VALIDATION_ERROR",
            )

        if "paid_at" in kwargs and kwargs["paid_at"] is not None:
            if kwargs["paid_at"] > datetime.utcnow():
                return _compat_error(
                    legacy_payload={"error": "'paid_at' não pode ser uma data futura."},
                    status_code=400,
                    message="'paid_at' não pode ser uma data futura.",
                    error_code="VALIDATION_ERROR",
                )

        resolved_is_recurring = bool(
            kwargs.get("is_recurring", transaction.is_recurring)
        )
        resolved_due_date = kwargs.get("due_date", transaction.due_date)
        resolved_start_date = kwargs.get("start_date", transaction.start_date)
        resolved_end_date = kwargs.get("end_date", transaction.end_date)
        recurring_error = _validate_recurring_payload(
            is_recurring=resolved_is_recurring,
            due_date=resolved_due_date,
            start_date=resolved_start_date,
            end_date=resolved_end_date,
        )
        if recurring_error:
            return _compat_error(
                legacy_payload={"error": recurring_error},
                status_code=400,
                message=recurring_error,
                error_code="VALIDATION_ERROR",
            )

        resolved_tag_id = kwargs["tag_id"] if "tag_id" in kwargs else transaction.tag_id
        resolved_account_id = (
            kwargs["account_id"] if "account_id" in kwargs else transaction.account_id
        )
        resolved_credit_card_id = (
            kwargs["credit_card_id"]
            if "credit_card_id" in kwargs
            else transaction.credit_card_id
        )
        reference_error = _enforce_transaction_reference_ownership_or_error(
            user_id=user_uuid,
            tag_id=resolved_tag_id,
            account_id=resolved_account_id,
            credit_card_id=resolved_credit_card_id,
        )
        if reference_error:
            return _compat_error(
                legacy_payload={"error": reference_error},
                status_code=400,
                message=reference_error,
                error_code="VALIDATION_ERROR",
            )

        try:
            _apply_transaction_updates(transaction, kwargs)

            db.session.commit()

            updated_data = serialize_transaction(transaction)

            return _compat_success(
                legacy_payload={
                    "message": "Transação atualizada com sucesso",
                    "transaction": updated_data,
                },
                status_code=200,
                message="Transação atualizada com sucesso",
                data={"transaction": updated_data},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao atualizar transação",
                log_context="transaction.update_failed",
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
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
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
            return _invalid_token_response()

        user_id = get_jwt_identity()
        transaction = Transaction.query.filter_by(
            id=transaction_id, deleted=False
        ).first()

        if transaction is None:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        if str(transaction.user_id) != str(user_id):
            return _compat_error(
                legacy_payload={
                    "error": "Você não tem permissão para deletar esta transação."
                },
                status_code=403,
                message="Você não tem permissão para deletar esta transação.",
                error_code="FORBIDDEN",
            )

        try:
            transaction.deleted = True
            db.session.commit()

            return _compat_success(
                legacy_payload={
                    "message": "Transação deletada com sucesso (soft delete)."
                },
                status_code=200,
                message="Transação deletada com sucesso (soft delete).",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao deletar transação",
                log_context="transaction.soft_delete_failed",
            )

    @doc(
        description=(
            "Restaura uma transação deletada logicamente.\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Transação restaurada com sucesso' }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "transaction_id": {"description": "ID da transação", "type": "string"},
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
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
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=user_uuid, deleted=True
        ).first()
        if not transaction:
            return _compat_error(
                legacy_payload={"error": "Transação não encontrada."},
                status_code=404,
                message="Transação não encontrada.",
                error_code="NOT_FOUND",
            )

        try:
            transaction.deleted = False
            db.session.commit()
            return _compat_success(
                legacy_payload={"message": "Transação restaurada com sucesso"},
                status_code=200,
                message="Transação restaurada com sucesso",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao restaurar transação",
                log_context="transaction.restore_failed",
            )

    @doc(
        description=(
            "Lista todas as transações deletadas "
            "(soft deleted) do usuário autenticado.\n\n"
            "Exemplo de resposta:\n"
            "{ 'deleted_transactions': [{...}] }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
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
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        try:
            transactions = Transaction.query.filter_by(
                user_id=user_uuid, deleted=True
            ).all()
            serialized = [serialize_transaction(item) for item in transactions]

            return _compat_success(
                legacy_payload={"deleted_transactions": serialized},
                status_code=200,
                message="Lista de transações deletadas",
                data={"deleted_transactions": serialized},
                meta={"total": len(serialized)},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar transações deletadas",
                log_context="transaction.list_deleted_failed",
            )

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
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Lista de transações"},
            401: {"description": "Token inválido ou expirado"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get_active(self) -> Response:  # noqa: C901
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        try:
            page = _parse_positive_int(
                request.args.get("page"), default=1, field_name="page"
            )
            per_page = _parse_positive_int(
                request.args.get("per_page"),
                default=10,
                field_name="per_page",
            )

            transaction_type = request.args.get("type")
            status = request.args.get("status")
            start_date = _parse_optional_date(
                request.args.get("start_date"), "start_date"
            )
            end_date = _parse_optional_date(request.args.get("end_date"), "end_date")
            tag_id = _parse_optional_uuid(request.args.get("tag_id"), "tag_id")
            account_id = _parse_optional_uuid(
                request.args.get("account_id"), "account_id"
            )
            credit_card_id = _parse_optional_uuid(
                request.args.get("credit_card_id"), "credit_card_id"
            )

            if start_date and end_date and start_date > end_date:
                return _compat_error(
                    legacy_payload={
                        "error": (
                            "Parâmetro 'start_date' não pode ser maior que 'end_date'."
                        )
                    },
                    status_code=400,
                    message=(
                        "Parâmetro 'start_date' não pode ser maior que 'end_date'."
                    ),
                    error_code="VALIDATION_ERROR",
                )

            query = Transaction.query.filter_by(user_id=user_uuid, deleted=False)

            if transaction_type:
                try:
                    query = query.filter(
                        Transaction.type == TransactionType(transaction_type.lower())
                    )
                except ValueError:
                    return _compat_error(
                        legacy_payload={
                            "error": (
                                "Parâmetro 'type' inválido. "
                                "Use 'income' ou 'expense'."
                            )
                        },
                        status_code=400,
                        message=(
                            "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
                        ),
                        error_code="VALIDATION_ERROR",
                    )

            if status:
                try:
                    query = query.filter(
                        Transaction.status == TransactionStatus(status.lower())
                    )
                except ValueError:
                    return _compat_error(
                        legacy_payload={
                            "error": (
                                "Parâmetro 'status' inválido. "
                                "Use paid, pending, cancelled, postponed ou overdue."
                            )
                        },
                        status_code=400,
                        message=(
                            "Parâmetro 'status' inválido. "
                            "Use paid, pending, cancelled, postponed ou overdue."
                        ),
                        error_code="VALIDATION_ERROR",
                    )

            if start_date:
                query = query.filter(Transaction.due_date >= start_date)
            if end_date:
                query = query.filter(Transaction.due_date <= end_date)
            if tag_id:
                query = query.filter(Transaction.tag_id == tag_id)
            if account_id:
                query = query.filter(Transaction.account_id == account_id)
            if credit_card_id:
                query = query.filter(Transaction.credit_card_id == credit_card_id)

            total = query.count()
            pages = (total + per_page - 1) // per_page if total else 0
            transactions = (
                query.order_by(
                    Transaction.due_date.desc(), Transaction.created_at.desc()
                )
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )

            serialized = [serialize_transaction(item) for item in transactions]

            return _compat_success(
                legacy_payload={
                    "transactions": serialized,
                    "total": total,
                    "page": page,
                    "per_page": per_page,
                },
                status_code=200,
                message="Lista de transações ativas",
                data={"transactions": serialized},
                meta={
                    "pagination": {
                        "total": total,
                        "page": page,
                        "per_page": per_page,
                        "pages": pages,
                    }
                },
            )
        except ValueError as exc:
            return _compat_error(
                legacy_payload={"error": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar transações ativas",
                log_context="transaction.list_active_failed",
            )


class TransactionSummaryResource(MethodResource):
    @doc(
        description=(
            "Resumo mensal das transações (total de receitas e despesas).\n\n"
            "Parâmetro obrigatório: month=YYYY-MM.\n\n"
            "Exemplo de resposta:\n"
            "{ 'month': '2024-02', 'income_total': 5000.00, "
            "'expense_total': 3000.00, ... }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "description": "Formato YYYY-MM (ex: 2025-04)",
                "in": "query",
                "type": "string",
            },
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
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
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)
        try:
            year, month_number, month = _parse_month_param(request.args.get("month"))
            analytics = TransactionAnalyticsService(user_uuid)
            transactions = analytics.get_month_transactions(
                year=year, month_number=month_number
            )
            aggregates = analytics.get_month_aggregates(
                year=year, month_number=month_number
            )

            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))

            serialized = [serialize_transaction(item) for item in transactions]
            paginated = PaginatedResponse.format(
                serialized, len(transactions), page, page_size
            )

            return _compat_success(
                legacy_payload={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
                    **paginated,
                },
                status_code=200,
                message="Resumo mensal calculado com sucesso",
                data={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
                    "items": paginated["data"],
                },
                meta={
                    "pagination": {
                        "total": paginated["total"],
                        "page": paginated["page"],
                        "per_page": paginated["page_size"],
                        "has_next_page": paginated["has_next_page"],
                    }
                },
            )
        except ValueError as exc:
            return _compat_error(
                legacy_payload={"error": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao calcular resumo mensal",
                log_context="transaction.monthly_summary_failed",
            )


class TransactionMonthlyDashboardResource(MethodResource):
    @doc(
        description=(
            "Dashboard mensal de transações com totais, contagens e categorias "
            "principais.\n\n"
            "Parâmetro obrigatório: month=YYYY-MM.\n\n"
            "Métricas retornadas:\n"
            "- income_total, expense_total, balance\n"
            "- contagens por tipo e por status\n"
            "- top categorias de despesas e receitas"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "month": {
                "description": "Formato YYYY-MM (ex: 2025-04)",
                "in": "query",
                "type": "string",
            },
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Dashboard mensal de transações"},
            400: {"description": "Parâmetro inválido"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        try:
            year, month_number, month = _parse_month_param(request.args.get("month"))
            analytics = TransactionAnalyticsService(user_uuid)
            aggregates = analytics.get_month_aggregates(
                year=year,
                month_number=month_number,
            )
            status_counts = analytics.get_status_counts(
                year=year, month_number=month_number
            )
            top_expense_categories = analytics.get_top_categories(
                year=year,
                month_number=month_number,
                transaction_type=TransactionType.EXPENSE,
            )
            top_income_categories = analytics.get_top_categories(
                year=year,
                month_number=month_number,
                transaction_type=TransactionType.INCOME,
            )

            return _compat_success(
                legacy_payload={
                    "month": month,
                    "income_total": float(aggregates["income_total"]),
                    "expense_total": float(aggregates["expense_total"]),
                    "balance": float(aggregates["balance"]),
                    "counts": {
                        "total_transactions": aggregates["total_transactions"],
                        "income_transactions": aggregates["income_transactions"],
                        "expense_transactions": aggregates["expense_transactions"],
                        "status": status_counts,
                    },
                    "top_expense_categories": top_expense_categories,
                    "top_income_categories": top_income_categories,
                },
                status_code=200,
                message="Dashboard mensal calculado com sucesso",
                data={
                    "month": month,
                    "totals": {
                        "income_total": float(aggregates["income_total"]),
                        "expense_total": float(aggregates["expense_total"]),
                        "balance": float(aggregates["balance"]),
                    },
                    "counts": {
                        "total_transactions": aggregates["total_transactions"],
                        "income_transactions": aggregates["income_transactions"],
                        "expense_transactions": aggregates["expense_transactions"],
                        "status": status_counts,
                    },
                    "top_categories": {
                        "expense": top_expense_categories,
                        "income": top_income_categories,
                    },
                },
            )
        except ValueError as exc:
            return _compat_error(
                legacy_payload={"error": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao calcular dashboard mensal",
                log_context="transaction.monthly_dashboard_failed",
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
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
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
            return _invalid_token_response()

        user_id = get_jwt_identity()

        transaction = Transaction.query.filter_by(
            id=transaction_id, user_id=UUID(user_id), deleted=True
        ).first()

        if not transaction:
            return _compat_error(
                legacy_payload={
                    "error": "Transação não encontrada ou não está deletada."
                },
                status_code=404,
                message="Transação não encontrada ou não está deletada.",
                error_code="NOT_FOUND",
            )

        try:
            db.session.delete(transaction)
            db.session.commit()
            return _compat_success(
                legacy_payload={"message": "Transação removida permanentemente."},
                status_code=200,
                message="Transação removida permanentemente.",
                data={},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao deletar permanentemente",
                log_context="transaction.force_delete_failed",
            )


class TransactionDeletedResource(MethodResource):
    @doc(
        description=(
            "Lista todas as transações deletadas "
            "(soft deleted) do usuário autenticado.\n\n"
            "Exemplo de resposta:\n"
            "{ 'deleted_transactions': [{...}] }"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            200: {"description": "Lista de transações deletadas"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get(self) -> Response:
        resource = TransactionResource()
        return resource.get_deleted()


class TransactionListActiveResource(MethodResource):
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
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Lista de transações"},
            401: {"description": "Token inválido ou expirado"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore
    @jwt_required()  # type: ignore
    def get(self) -> Response:
        resource = TransactionResource()
        return resource.get_active()


class TransactionExpensePeriodResource(MethodResource):
    @doc(
        description=(
            "Lista despesas por período do usuário autenticado.\n\n"
            "Regras:\n"
            "- É obrigatório enviar ao menos um parâmetro: startDate ou finalDate\n"
            "- startDate e finalDate usam formato YYYY-MM-DD\n"
            "- paginação com page e per_page\n"
            "- ordenação com order_by e order\n\n"
            "Métricas retornadas:\n"
            "- total_transactions (total no período)\n"
            "- income_transactions (receitas no período)\n"
            "- expense_transactions (despesas no período)"
        ),
        tags=["Transações"],
        security=[{"BearerAuth": []}],
        params={
            "startDate": {"description": "Data inicial (YYYY-MM-DD)", "type": "string"},
            "finalDate": {"description": "Data final (YYYY-MM-DD)", "type": "string"},
            "page": {"description": "Número da página", "type": "integer"},
            "per_page": {"description": "Itens por página", "type": "integer"},
            "order_by": {
                "description": "Campo de ordenação: due_date|created_at|amount|title",
                "type": "string",
            },
            "order": {"description": "Direção: asc|desc", "type": "string"},
            CONTRACT_HEADER: {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Lista de despesas por período"},
            400: {"description": "Parâmetros inválidos"},
            401: {"description": "Token inválido"},
            500: {"description": "Erro interno"},
        },
    )  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    def get(self) -> Response:
        verify_jwt_in_request()
        jwt_data = get_jwt()
        if is_token_revoked(jwt_data["jti"]):
            return _invalid_token_response()

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        try:
            start_date = _parse_optional_date(
                request.args.get("startDate"), "startDate"
            )
            final_date = _parse_optional_date(
                request.args.get("finalDate"), "finalDate"
            )
            if not start_date and not final_date:
                return _compat_error(
                    legacy_payload={
                        "error": (
                            "Informe ao menos um parâmetro: 'startDate' ou 'finalDate'."
                        )
                    },
                    status_code=400,
                    message=(
                        "Informe ao menos um parâmetro: " "'startDate' ou 'finalDate'."
                    ),
                    error_code="VALIDATION_ERROR",
                )

            if start_date and final_date and start_date > final_date:
                return _compat_error(
                    legacy_payload={
                        "error": (
                            "Parâmetro 'startDate' não pode ser maior que "
                            "'finalDate'."
                        )
                    },
                    status_code=400,
                    message=(
                        "Parâmetro 'startDate' não pode ser maior que " "'finalDate'."
                    ),
                    error_code="VALIDATION_ERROR",
                )

            page = _parse_positive_int(
                request.args.get("page"), default=1, field_name="page"
            )
            per_page = _parse_positive_int(
                request.args.get("per_page"), default=10, field_name="per_page"
            )
            order_by = str(request.args.get("order_by", "due_date")).strip().lower()
            order = str(request.args.get("order", "desc")).strip().lower()
            ordering_clause = _resolve_transaction_ordering(order_by, order)

            base_query = Transaction.query.filter_by(user_id=user_uuid, deleted=False)
            if start_date:
                base_query = base_query.filter(Transaction.due_date >= start_date)
            if final_date:
                base_query = base_query.filter(Transaction.due_date <= final_date)

            total_transactions = base_query.count()
            income_transactions = base_query.filter(
                Transaction.type == TransactionType.INCOME
            ).count()
            expense_transactions = base_query.filter(
                Transaction.type == TransactionType.EXPENSE
            ).count()

            expenses_query = base_query.filter(
                Transaction.type == TransactionType.EXPENSE
            )
            total_expenses = expense_transactions
            pages = (total_expenses + per_page - 1) // per_page if total_expenses else 0
            expenses = (
                expenses_query.order_by(ordering_clause)
                .offset((page - 1) * per_page)
                .limit(per_page)
                .all()
            )
            serialized_expenses = [serialize_transaction(item) for item in expenses]

            counts_payload = {
                "total_transactions": total_transactions,
                "income_transactions": income_transactions,
                "expense_transactions": expense_transactions,
            }

            return _compat_success(
                legacy_payload={
                    "expenses": serialized_expenses,
                    "total": total_expenses,
                    "page": page,
                    "per_page": per_page,
                    "counts": counts_payload,
                },
                status_code=200,
                message="Lista de despesas por período",
                data={"expenses": serialized_expenses, "counts": counts_payload},
                meta={
                    "pagination": {
                        "total": total_expenses,
                        "page": page,
                        "per_page": per_page,
                        "pages": pages,
                    }
                },
            )
        except ValueError as exc:
            return _compat_error(
                legacy_payload={"error": str(exc)},
                status_code=400,
                message=str(exc),
                error_code="VALIDATION_ERROR",
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao buscar despesas por período",
                log_context="transaction.expenses_period_failed",
            )


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
    view_func=TransactionDeletedResource.as_view("transaction_list_deleted"),
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
    "/dashboard",
    view_func=TransactionMonthlyDashboardResource.as_view(
        "transaction_monthly_dashboard"
    ),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/list",
    view_func=TransactionListActiveResource.as_view("transaction_list_active"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/expenses",
    view_func=TransactionExpensePeriodResource.as_view("transaction_expense_period"),
    methods=["GET"],
)
