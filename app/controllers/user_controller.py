from datetime import datetime
from typing import Any, Callable, Dict, Union, cast
from uuid import UUID

from flask import Blueprint, Response, has_request_context, jsonify, request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from sqlalchemy import extract
from sqlalchemy.orm.query import Query

from app.extensions.database import db
from app.models.transaction import Transaction
from app.models.user import User
from app.models.wallet import Wallet
from app.schemas.user_schemas import UserProfileSchema
from app.utils.pagination import PaginatedResponse
from app.utils.response_builder import error_payload, success_payload

JSON_MIMETYPE = "application/json"
CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"

user_bp = Blueprint("user", __name__, url_prefix="/user")


def _is_v2_contract() -> bool:
    if not has_request_context():
        return False
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def _compat_success(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    data: Dict[str, Any],
    meta: Dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if _is_v2_contract():
        payload = success_payload(message=message, data=data, meta=meta)
    return Response(
        jsonify(payload).get_data(),
        status=status_code,
        mimetype=JSON_MIMETYPE,
    )


def _compat_error(
    *,
    legacy_payload: Dict[str, Any],
    status_code: int,
    message: str,
    error_code: str,
    details: Dict[str, Any] | None = None,
) -> Response:
    payload = legacy_payload
    if _is_v2_contract():
        payload = error_payload(message=message, code=error_code, details=details)
    return Response(
        jsonify(payload).get_data(),
        status=status_code,
        mimetype=JSON_MIMETYPE,
    )


def _serialize_user_profile(user: User) -> Dict[str, Any]:
    return {
        "id": str(user.id),
        "name": user.name,
        "email": user.email,
        "gender": user.gender,
        "birth_date": str(user.birth_date) if user.birth_date else None,
        "monthly_income": float(user.monthly_income) if user.monthly_income else None,
        "net_worth": float(user.net_worth) if user.net_worth else None,
        "monthly_expenses": (
            float(user.monthly_expenses) if user.monthly_expenses else None
        ),
        "initial_investment": (
            float(user.initial_investment) if user.initial_investment else None
        ),
        "monthly_investment": (
            float(user.monthly_investment) if user.monthly_investment else None
        ),
        "investment_goal_date": (
            str(user.investment_goal_date) if user.investment_goal_date else None
        ),
    }


def assign_user_profile_fields(
    user: User, data: Dict[str, Any]
) -> Dict[str, Union[str, bool]]:
    date_fields = ["birth_date", "investment_goal_date"]
    for field in [
        "gender",
        "birth_date",
        "monthly_income",
        "net_worth",
        "monthly_expenses",
        "initial_investment",
        "monthly_investment",
        "investment_goal_date",
    ]:
        if field in data:
            value = data[field]
            if field in date_fields and isinstance(value, str):
                try:
                    value = datetime.strptime(value, "%Y-%m-%d").date()
                except ValueError:
                    return {
                        "error": True,
                        "message": (
                            f"Formato inválido para '{field}'. Use 'YYYY-MM-DD'."
                        ),
                    }
            setattr(user, field, value)
    return {"error": False}


def validate_user_token(user_id: UUID, jti: str) -> Union[User, Response]:
    user = User.query.get(user_id)
    if not user or not hasattr(user, "current_jti") or user.current_jti != jti:
        return _compat_error(
            legacy_payload={"message": "Token revogado ou usuário não encontrado"},
            status_code=401,
            message="Token revogado ou usuário não encontrado",
            error_code="UNAUTHORIZED",
        )
    return user


def filter_transactions(
    user_id: UUID, status: str, month: str
) -> Union[Query, Response]:
    query = Transaction.query.filter_by(user_id=user_id, deleted=False)

    if status:
        try:
            from app.models.transaction import TransactionStatus

            query = query.filter(
                Transaction.status == TransactionStatus(status.lower())
            )
        except ValueError:
            return _compat_error(
                legacy_payload={"message": f"Status inválido: {status}"},
                status_code=400,
                message=f"Status inválido: {status}",
                error_code="VALIDATION_ERROR",
            )

    if month:
        try:
            year, month_num = map(int, month.split("-"))
            query = query.filter(
                extract("year", Transaction.due_date) == year,
                extract("month", Transaction.due_date) == month_num,
            )
        except ValueError:
            return _compat_error(
                legacy_payload={
                    "message": "Parâmetro 'month' inválido. Use o formato YYYY-MM"
                },
                status_code=400,
                message="Parâmetro 'month' inválido. Use o formato YYYY-MM",
                error_code="VALIDATION_ERROR",
            )

    return query


class UserProfileResource(MethodResource):
    @doc(
        description=(
            "Atualiza o perfil do usuário autenticado.\n\n"
            "Campos aceitos:\n"
            "- gender: 'masculino', 'feminino', 'outro'\n"
            "- birth_date: 'YYYY-MM-DD'\n"
            """- monthly_income, net_worth, monthly_expenses, initial_investment,
            monthly_investment: decimal\n"""
            "- investment_goal_date: 'YYYY-MM-DD'\n\n"
            "Exemplo de request:\n"
            """{\n  'gender': 'masculino', 'birth_date': '1990-05-15',
            'monthly_income': '5000.00',
            'net_worth': '100000.00',
            'monthly_expenses': '2000.00',
            'initial_investment': '10000.00',
            'monthly_investment': '500.00',
            'investment_goal_date': '2025-12-31' }\n\n"""
            "Exemplo de resposta:\n"
            "{ 'message': 'Perfil atualizado com sucesso', "
            "'data': { ...dados do usuário... } }"
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params={
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            }
        },
        responses={
            200: {"description": "Perfil atualizado com sucesso"},
            400: {"description": "Erro de validação"},
            401: {"description": "Token revogado"},
            404: {"description": "Usuário não encontrado"},
            500: {"description": "Erro ao atualizar perfil"},
        },
    )  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(UserProfileSchema(), location="json")  # type: ignore[misc]
    def put(self, **kwargs: Any) -> Response:
        user_id = UUID(get_jwt_identity())
        jti = get_jwt()["jti"]
        user = User.query.get(user_id)
        if not user:
            return _compat_error(
                legacy_payload={"message": "Usuário não encontrado"},
                status_code=404,
                message="Usuário não encontrado",
                error_code="NOT_FOUND",
            )

        if not hasattr(user, "current_jti") or user.current_jti != jti:
            return _compat_error(
                legacy_payload={"message": "Token revogado"},
                status_code=401,
                message="Token revogado",
                error_code="UNAUTHORIZED",
            )

        data = kwargs

        result = assign_user_profile_fields(user, data)
        if result["error"]:
            return _compat_error(
                legacy_payload={"message": result["message"]},
                status_code=400,
                message=str(result["message"]),
                error_code="VALIDATION_ERROR",
            )

        # Validação de dados
        errors = user.validate_profile_data()
        if errors:
            return _compat_error(
                legacy_payload={"message": "Erro de validação", "errors": errors},
                status_code=400,
                message="Erro de validação",
                error_code="VALIDATION_ERROR",
                details={"errors": errors},
            )

        try:
            db.session.commit()
            user_data = _serialize_user_profile(user)
            return _compat_success(
                legacy_payload={
                    "message": "Perfil atualizado com sucesso",
                    "data": user_data,
                },
                status_code=200,
                message="Perfil atualizado com sucesso",
                data={"user": user_data},
            )
        except Exception as e:
            return _compat_error(
                legacy_payload={"message": "Erro ao atualizar perfil", "error": str(e)},
                status_code=500,
                message="Erro ao atualizar perfil",
                error_code="INTERNAL_ERROR",
                details={"exception": str(e)},
            )


class UserMeResource(MethodResource):
    @doc(
        description=(
            "Retorna os dados do usuário autenticado e suas transações paginadas.\n\n"
            "Filtros disponíveis:\n"
            "- page: número da página\n"
            "- limit: itens por página\n"
            "- status: status da transação (paid, pending, cancelled, postponed)\n"
            "- month: filtra transações pelo mês (YYYY-MM)\n\n"
            "Exemplo de resposta:\n"
            """{\n  'user': { 'id': '...', 'name': '...', ... },\n
            'transactions': { 'items': [...], 'total': 10, ... }\n}"""
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params={
            "page": {"description": "Número da página", "type": "integer"},
            "limit": {"description": "Itens por página", "type": "integer"},
            "status": {"description": "Status da transação", "type": "string"},
            "month": {"description": "Mês no formato YYYY-MM", "type": "string"},
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Dados do usuário e transações paginadas"},
            401: {"description": "Token inválido ou expirado"},
        },
    )  # type: ignore
    @cast(Callable[..., Response], jwt_required())
    def get(self) -> Response:
        user_id = UUID(get_jwt_identity())
        jti = get_jwt()["jti"]
        user_or_response = validate_user_token(user_id, jti)
        if isinstance(user_or_response, Response):
            return user_or_response
        user = user_or_response

        # Paginação e filtros
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 10))
        status = request.args.get("status")
        month = request.args.get("month")

        query_or_response = filter_transactions(user.id, status, month)
        if isinstance(query_or_response, Response):
            return query_or_response
        query = query_or_response

        pagination = query.order_by(Transaction.due_date.desc()).paginate(
            page=page, per_page=limit, error_out=False
        )
        transactions = [
            {
                "id": str(t.id),
                "title": t.title,
                "amount": str(t.amount),
                "type": t.type.value,
                "due_date": t.due_date.isoformat(),
                "status": t.status.value,
                "description": t.description,
                "observation": t.observation,
                "is_recurring": t.is_recurring,
                "is_installment": t.is_installment,
                "installment_count": t.installment_count,
                "tag_id": str(t.tag_id) if t.tag_id else None,
                "account_id": str(t.account_id) if t.account_id else None,
                "credit_card_id": str(t.credit_card_id) if t.credit_card_id else None,
                "currency": t.currency,
                "created_at": t.created_at.isoformat() if t.created_at else None,
                "updated_at": t.updated_at.isoformat() if t.updated_at else None,
            }
            for t in pagination.items
        ]
        paginated_transactions = PaginatedResponse.format(
            transactions, pagination.total, pagination.page, pagination.per_page
        )

        wallet_items = Wallet.query.filter_by(user_id=user.id).all()
        wallet_data = [
            {
                "id": str(w.id),
                "name": w.name,
                "value": float(w.value) if w.value is not None else None,
                "estimated_value_on_create_date": (
                    float(w.estimated_value_on_create_date)
                    if w.estimated_value_on_create_date is not None
                    else None
                ),
                "ticker": w.ticker,
                "quantity": w.quantity,
                "asset_class": w.asset_class,
                "annual_rate": (
                    float(w.annual_rate) if w.annual_rate is not None else None
                ),
                "target_withdraw_date": (
                    str(w.target_withdraw_date) if w.target_withdraw_date else None
                ),
                "register_date": str(w.register_date),
                "should_be_on_wallet": w.should_be_on_wallet,
            }
            for w in wallet_items
        ]

        user_data = _serialize_user_profile(user)
        legacy_payload = {
            "user": user_data,
            "transactions": paginated_transactions,
            "wallet": wallet_data,
        }
        return _compat_success(
            legacy_payload=legacy_payload,
            status_code=200,
            message="Dados do usuário retornados com sucesso",
            data={
                "user": user_data,
                "transactions": {
                    "items": paginated_transactions["data"],
                    "total": paginated_transactions["total"],
                    "page": paginated_transactions["page"],
                    "per_page": paginated_transactions["page_size"],
                    "has_next_page": paginated_transactions["has_next_page"],
                },
                "wallet": wallet_data,
            },
            meta={
                "pagination": {
                    "total": paginated_transactions["total"],
                    "page": paginated_transactions["page"],
                    "per_page": paginated_transactions["page_size"],
                    "has_next_page": paginated_transactions["has_next_page"],
                }
            },
        )


user_bp.add_url_rule(
    "/profile", view_func=UserProfileResource.as_view("profile"), methods=["PUT"]
)
user_bp.add_url_rule("/me", view_func=UserMeResource.as_view("me"))
