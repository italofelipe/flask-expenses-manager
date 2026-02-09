from datetime import date, datetime
from decimal import Decimal
from typing import Any, Dict
from uuid import UUID

from flask import Blueprint, Response, has_request_context, jsonify, request
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
from app.utils.response_builder import error_payload, success_payload

transaction_bp = Blueprint("transaction", __name__, url_prefix="/transactions")

INVALID_TOKEN_MESSAGE = "Token inválido."
CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"


def _is_v2_contract() -> bool:
    if not has_request_context():
        return False
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def _json_response(payload: Dict[str, Any], status_code: int) -> Response:
    response = jsonify(payload)
    response.status_code = status_code
    return response


def _compat_success(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    data: Dict[str, Any],
    meta: Dict[str, Any] | None = None,
) -> Response:
    if _is_v2_contract():
        return _json_response(
            success_payload(message=message, data=data, meta=meta),
            status_code,
        )
    return _json_response(legacy_payload, status_code)


def _compat_error(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: Dict[str, Any] | None = None,
) -> Response:
    if _is_v2_contract():
        return _json_response(
            error_payload(message=message, code=error_code, details=details),
            status_code,
        )
    return _json_response(legacy_payload, status_code)


def _parse_positive_int(value: str | None, *, default: int, field_name: str) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except ValueError as exc:
        raise ValueError(
            f"Parâmetro '{field_name}' inválido. Informe um inteiro positivo."
        ) from exc
    if parsed < 1:
        raise ValueError(
            f"Parâmetro '{field_name}' inválido. Informe um inteiro positivo."
        )
    return parsed


def _parse_optional_uuid(value: str | None, field_name: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except ValueError as exc:
        raise ValueError(
            f"Parâmetro '{field_name}' inválido. Informe um UUID válido."
        ) from exc


def _parse_optional_date(value: str | None, field_name: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
        ) from exc


def _validate_recurring_payload(
    *,
    is_recurring: bool,
    due_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> str | None:
    if not is_recurring:
        if start_date and end_date and start_date > end_date:
            return "Parâmetro 'start_date' não pode ser maior que 'end_date'."
        return None

    if not start_date or not end_date:
        return (
            "Transações recorrentes exigem 'start_date' e 'end_date' "
            "no formato YYYY-MM-DD."
        )

    if start_date > end_date:
        return "Parâmetro 'start_date' não pode ser maior que 'end_date'."

    if due_date is None:
        return "Transações recorrentes exigem 'due_date' no formato YYYY-MM-DD."

    if due_date < start_date or due_date > end_date:
        return "Parâmetro 'due_date' deve estar entre 'start_date' e 'end_date'."

    return None


def _resolve_transaction_ordering(order_by: str, order: str) -> Any:
    allowed_order_by: Dict[str, Any] = {
        "due_date": Transaction.due_date,
        "created_at": Transaction.created_at,
        "amount": Transaction.amount,
        "title": Transaction.title,
    }
    if order_by not in allowed_order_by:
        raise ValueError(
            "Parâmetro 'order_by' inválido. Use due_date, created_at, amount ou title."
        )
    if order not in {"asc", "desc"}:
        raise ValueError("Parâmetro 'order' inválido. Use asc ou desc.")

    column = allowed_order_by[order_by]
    return column.asc() if order == "asc" else column.desc()


def _invalid_token_response() -> Response:
    return _compat_error(
        legacy_payload={"error": INVALID_TOKEN_MESSAGE},
        status_code=401,
        message=INVALID_TOKEN_MESSAGE,
        error_code="UNAUTHORIZED",
    )


def serialize_transaction(transaction: Transaction) -> Dict[str, Any]:
    return {
        "id": str(transaction.id),
        "title": transaction.title,
        "amount": str(transaction.amount),
        "type": transaction.type.value,
        "due_date": transaction.due_date.isoformat(),
        "start_date": (
            transaction.start_date.isoformat() if transaction.start_date else None
        ),
        "end_date": transaction.end_date.isoformat() if transaction.end_date else None,
        "description": transaction.description,
        "observation": transaction.observation,
        "is_recurring": transaction.is_recurring,
        "is_installment": transaction.is_installment,
        "installment_count": transaction.installment_count,
        "tag_id": str(transaction.tag_id) if transaction.tag_id else None,
        "account_id": str(transaction.account_id) if transaction.account_id else None,
        "credit_card_id": (
            str(transaction.credit_card_id) if transaction.credit_card_id else None
        ),
        "status": transaction.status.value,
        "currency": transaction.currency,
        "created_at": (
            transaction.created_at.isoformat() if transaction.created_at else None
        ),
        "updated_at": (
            transaction.updated_at.isoformat() if transaction.updated_at else None
        ),
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

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            from uuid import uuid4

            from dateutil.relativedelta import relativedelta

            try:
                group_id = uuid4()
                total = Decimal(kwargs["amount"])
                count = int(kwargs["installment_count"])
                base_date = kwargs["due_date"]
                value = round(total / count, 2)
                title = kwargs["title"]
                if "type" in kwargs:
                    kwargs["type"] = kwargs["type"].lower()

                transactions = []
                for i in range(count):
                    due = base_date + relativedelta(months=i)
                    transaction = Transaction(
                        user_id=UUID(user_id),
                        title=f"{title} ({i + 1}/{count})",
                        amount=value,
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
            except Exception as exc:
                db.session.rollback()
                return _compat_error(
                    legacy_payload={
                        "error": "Erro ao criar transações parceladas",
                        "message": str(exc),
                    },
                    status_code=500,
                    message="Erro ao criar transações parceladas",
                    error_code="INTERNAL_ERROR",
                    details={"exception": str(exc)},
                )

        try:
            transaction = Transaction(
                user_id=UUID(user_id),
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao criar transação",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao criar transação",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
            )

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

        try:
            for field, value in kwargs.items():
                if hasattr(transaction, field):
                    setattr(transaction, field, value)

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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao atualizar transação",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao atualizar transação",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao deletar transação",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao deletar transação",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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

        if not transaction.deleted:
            return _compat_error(
                legacy_payload={"error": "Transação não está deletada."},
                status_code=400,
                message="Transação não está deletada.",
                error_code="VALIDATION_ERROR",
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao restaurar transação",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao restaurar transação",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao buscar transações deletadas",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao buscar transações deletadas",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao buscar transações ativas",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao buscar transações ativas",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        month = request.args.get("month")
        if not month:
            return _compat_error(
                legacy_payload={
                    "error": "Parâmetro 'month' é obrigatório no formato YYYY-MM."
                },
                status_code=400,
                message="Parâmetro 'month' é obrigatório no formato YYYY-MM.",
                error_code="VALIDATION_ERROR",
            )

        try:
            year, month_number = map(int, month.split("-"))
        except ValueError:
            return _compat_error(
                legacy_payload={"error": "Formato de mês inválido. Use YYYY-MM."},
                status_code=400,
                message="Formato de mês inválido. Use YYYY-MM.",
                error_code="VALIDATION_ERROR",
            )

        try:
            transactions = (
                Transaction.query.filter_by(user_id=user_uuid, deleted=False)
                .filter(db.extract("year", Transaction.due_date) == year)
                .filter(db.extract("month", Transaction.due_date) == month_number)
                .all()
            )

            income_total = sum(
                item.amount
                for item in transactions
                if item.type == TransactionType.INCOME
            )
            expense_total = sum(
                item.amount
                for item in transactions
                if item.type == TransactionType.EXPENSE
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
                    "income_total": float(income_total),
                    "expense_total": float(expense_total),
                    **paginated,
                },
                status_code=200,
                message="Resumo mensal calculado com sucesso",
                data={
                    "month": month,
                    "income_total": float(income_total),
                    "expense_total": float(expense_total),
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao calcular resumo mensal",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao calcular resumo mensal",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao deletar permanentemente",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao deletar permanentemente",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
        except Exception as exc:
            db.session.rollback()
            return _compat_error(
                legacy_payload={
                    "error": "Erro ao buscar despesas por período",
                    "message": str(exc),
                },
                status_code=500,
                message="Erro ao buscar despesas por período",
                error_code="INTERNAL_ERROR",
                details={"exception": str(exc)},
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
    "/list",
    view_func=TransactionListActiveResource.as_view("transaction_list_active"),
    methods=["GET"],
)

transaction_bp.add_url_rule(
    "/expenses",
    view_func=TransactionExpensePeriodResource.as_view("transaction_expense_period"),
    methods=["GET"],
)
