# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any, Callable, cast
from uuid import UUID

from flask import Response, request
from flask_apispec import doc
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.models.transaction import Transaction
from app.utils.pagination import PaginatedResponse

from .contracts import compat_success
from .dependencies import get_user_dependencies
from .helpers import (
    _serialize_user_profile,
    _validation_error_response,
    filter_transactions,
    validate_user_token,
)


def _parse_positive_int_compat(
    raw_value: str | None,
    *,
    default: int,
    field_name: str,
    max_value: int,
) -> int:
    # Preserve legacy monkeypatch target:
    # app.controllers.user_controller._parse_positive_int
    from app.controllers import user_controller as legacy_user_controller

    return legacy_user_controller._parse_positive_int(
        raw_value,
        default=default,
        field_name=field_name,
        max_value=max_value,
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
    )
    @cast(Callable[..., Response], jwt_required())
    def get(self) -> Response:
        user_id = UUID(get_jwt_identity())
        jti = get_jwt()["jti"]
        user_or_response = validate_user_token(user_id, jti)
        if isinstance(user_or_response, Response):
            return user_or_response
        user = user_or_response

        try:
            page = _parse_positive_int_compat(
                request.args.get("page"),
                default=1,
                field_name="page",
                max_value=10_000,
            )
            limit = _parse_positive_int_compat(
                request.args.get("limit"),
                default=10,
                field_name="limit",
                max_value=100,
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetros de paginação inválidos.",
            )
        status = request.args.get("status")
        month = request.args.get("month")

        query_or_response = filter_transactions(user.id, status, month)
        if isinstance(query_or_response, Response):
            return query_or_response
        query = query_or_response

        pagination = cast(Any, query.order_by(Transaction.due_date.desc())).paginate(
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

        dependencies = get_user_dependencies()
        wallet_items = dependencies.list_wallet_entries_by_user_id(user.id)
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
        return compat_success(
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
