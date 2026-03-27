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
        description=(
            "Retorna o bootstrap explícito da home do usuário autenticado.\n\n"
            "Ownership:\n"
            "- `/user/me` (`v3`) = contexto autenticado canônico\n"
            "- `/transactions` = coleção e filtros completos\n"
            "- `/wallet` = coleção canônica de carteira\n"
            "- `/user/bootstrap` = agregado leve para reduzir round-trips na home\n\n"
            "O bootstrap não substitui endpoints canônicos de coleção e expõe apenas "
            "um preview recente de transações."
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
            "X-API-Contract": {
                "in": "header",
                "description": (
                    "Opcional. Recomendado enviar `v2` ou `v3` para envelope "
                    "padronizado."
                ),
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Bootstrap retornado com sucesso"},
            400: {"description": "Erro de validação"},
            401: {"description": "Token inválido ou expirado"},
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
