from __future__ import annotations

from typing import Any, cast

from flask import Response, request
from flask_apispec.views import MethodResource

from app.application.services.authenticated_user_context_service import (
    AuthenticatedUserContextService,
)
from app.auth import get_active_auth_context
from app.models.transaction import Transaction
from app.services.authenticated_user_payloads import (
    to_authenticated_user_canonical_payload,
)
from app.utils.pagination import PaginatedResponse
from app.utils.response_builder import json_response, success_payload
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success, is_v3_contract_request
from .helpers import (
    _validation_error_response,
    filter_transactions,
    validate_user_token,
)
from .presenters import to_user_profile_payload, to_wallet_payload

COLLECTION_QUERY_PARAMS = ("page", "limit", "status", "month")


def _has_collection_semantics() -> bool:
    return any(request.args.get(field) is not None for field in COLLECTION_QUERY_PARAMS)


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
            "Retorna o contexto do usuário autenticado.\n\n"
            "Contrato canônico (`X-API-Contract: v3`): retorna apenas identidade, "
            "perfil, perfil financeiro, perfil investidor e contexto de produto.\n\n"
            "Contratos legados (`v1`/`v2`): mantêm transações paginadas e carteira.\n\n"
            "Filtros legados disponíveis apenas em `v1`/`v2`:\n"
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
                "description": (
                    "Opcional. `v2` mantém shape legado padronizado; `v3` "
                    "publica o contrato canônico sem coleções."
                ),
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Dados do usuário e transações paginadas"},
            401: {"description": "Token inválido ou expirado"},
        },
    )
    @jwt_required()
    def get(self) -> Response:
        auth_context = get_active_auth_context()
        user_or_response = validate_user_token(auth_context)
        if isinstance(user_or_response, Response):
            return user_or_response
        user = user_or_response

        context_service = AuthenticatedUserContextService.with_defaults()
        authenticated_user_context = context_service.build_context(user)

        if is_v3_contract_request():
            if _has_collection_semantics():
                return _validation_error_response(
                    exc=ValueError("collection semantics not supported"),
                    fallback_message=(
                        "O contrato canônico de '/user/me' não aceita paginação "
                        "nem filtros de coleção. Use '/transactions' ou o "
                        "bootstrap dedicado."
                    ),
                )
            return json_response(
                success_payload(
                    message="Contexto autenticado retornado com sucesso",
                    data={
                        "user": to_authenticated_user_canonical_payload(
                            authenticated_user_context.profile
                        )
                    },
                ),
                status_code=200,
            )

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

        user_data = to_user_profile_payload(authenticated_user_context.profile)
        wallet_data = to_wallet_payload(authenticated_user_context.wallet_entries)
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
