from __future__ import annotations

from typing import Any, cast

from flask import Response, request
from flask_apispec.views import MethodResource

from app.application.services.authenticated_user_bootstrap_service import (
    DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT,
    MAX_BOOTSTRAP_TRANSACTIONS_LIMIT,
    AuthenticatedUserBootstrapService,
)
from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_success_response,
)
from app.services.authenticated_user_payloads import (
    to_authenticated_user_bootstrap_payload,
)
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import compat_success
from .helpers import _validation_error_response, validate_user_token


def _parse_transactions_limit(raw_value: str | None) -> int:
    if raw_value is None:
        return DEFAULT_BOOTSTRAP_TRANSACTIONS_LIMIT
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            "Parâmetro 'transactions_limit' inválido. Informe um inteiro positivo."
        ) from exc
    if parsed < 1 or parsed > MAX_BOOTSTRAP_TRANSACTIONS_LIMIT:
        raise ValueError(
            "Parâmetro 'transactions_limit' inválido. Use um valor entre 1 e "
            f"{MAX_BOOTSTRAP_TRANSACTIONS_LIMIT}."
        )
    return parsed


class UserBootstrapResource(MethodResource):
    @doc(
        summary="Obter bootstrap da home do usuário",
        description=(
            "Retorna o bootstrap explícito da home do usuário autenticado.\n\n"
            "Ownership:\n"
            "- `/user/me` (`v3`) = contexto autenticado canônico\n"
            "- `/transactions` = coleção e filtros completos\n"
            "- `/wallet` = coleção canônica de carteira\n"
            "- `/user/bootstrap` = agregado leve para reduzir round-trips na home\n\n"
            "O bootstrap não substitui endpoints canônicos de coleção e expõe apenas "
            "previews recentes de transações e carteira."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params={
            "transactions_limit": {
                "description": (
                    "Opcional. Quantidade máxima de transações recentes no preview "
                    f"(1-{MAX_BOOTSTRAP_TRANSACTIONS_LIMIT})."
                ),
                "type": "integer",
                "required": False,
            },
            **contract_header_param(
                supported_version="v2_or_v3",
                description=(
                    "Opcional. Recomendado enviar `v2` ou `v3` para o envelope "
                    "padronizado."
                ),
            ),
        },
        responses={
            200: json_success_response(
                description="Bootstrap retornado com sucesso",
                message="Bootstrap do usuário retornado com sucesso",
                data_example={
                    "user": {
                        "identity": {
                            "id": "4b2ef64b-b35d-4ea2-a6f2-4ef3cfb295f1",
                            "name": "Italo",
                            "email": "italo@email.com",
                        },
                        "profile": {
                            "gender": "outro",
                            "birth_date": "1990-01-01",
                            "state_uf": "SP",
                            "occupation": "Founder",
                        },
                        "financial_profile": {
                            "monthly_income_net": 1000.0,
                            "monthly_expenses": 500.0,
                            "net_worth": 2000.0,
                            "initial_investment": 200.0,
                            "monthly_investment": 100.0,
                            "investment_goal_date": "2026-12-31",
                        },
                        "investor_profile": {
                            "declared": "conservador",
                            "suggested": "moderado",
                            "quiz_score": 8,
                            "taxonomy_version": "2026.1",
                            "financial_objectives": "crescer",
                        },
                        "product_context": {"entitlements_version": 3},
                    },
                    "transactions_preview": {
                        "items": [
                            {
                                "id": "cfef66a6-a148-49db-a72f-cc63b6080cf8",
                                "title": "Conta de luz",
                                "amount": "150.00",
                                "type": "expense",
                                "status": "pending",
                            }
                        ],
                        "limit": 5,
                        "returned_items": 1,
                        "has_more": False,
                    },
                    "wallet": {
                        "items": [
                            {
                                "id": "wallet-1",
                                "name": "Caixa",
                                "value": 100.0,
                                "quantity": 1,
                                "asset_class": "cash",
                            }
                        ],
                        "total": 8,
                        "returned_items": 1,
                        "limit": 5,
                        "has_more": True,
                    },
                },
            ),
            400: json_error_response(
                description="Erro de validação",
                message="Parâmetros do bootstrap inválidos.",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token inválido ou expirado",
                message="Token revogado",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        auth_context = get_active_auth_context()
        user_or_response = validate_user_token(auth_context)
        if isinstance(user_or_response, Response):
            return user_or_response

        try:
            transactions_limit = _parse_transactions_limit(
                request.args.get("transactions_limit")
            )
        except ValueError as exc:
            return _validation_error_response(
                exc=exc,
                fallback_message="Parâmetros do bootstrap inválidos.",
            )

        bootstrap = AuthenticatedUserBootstrapService.with_defaults().build_bootstrap(
            user_or_response,
            transactions_limit=transactions_limit,
        )
        payload = to_authenticated_user_bootstrap_payload(bootstrap)
        return compat_success(
            legacy_payload=cast(dict[str, Any], payload),
            status_code=200,
            message="Bootstrap do usuário retornado com sucesso",
            data=cast(dict[str, Any], payload),
        )


__all__ = ["UserBootstrapResource"]
