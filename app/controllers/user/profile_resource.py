from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app
from flask_apispec.views import MethodResource

from app.application.services.user_profile_service import update_user_profile
from app.auth import get_active_auth_context
from app.docs.openapi_helpers import (
    contract_header_param,
    json_error_response,
    json_request_body,
    json_success_response,
)
from app.extensions.database import db
from app.http.request_context import current_request_id
from app.schemas.user_schemas import UserProfileSchema
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_error, compat_success
from .dependencies import get_user_dependencies
from .helpers import _serialize_user_profile


class UserProfileResource(MethodResource):
    @doc(
        summary="Obter perfil reduzido do usuário",
        description=(
            "Retorna o perfil reduzido do usuário autenticado "
            "(sem transações e sem carteira)."
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        responses={
            200: json_success_response(
                description="Perfil retornado com sucesso",
                message="Perfil retornado com sucesso",
                data_example={
                    "user": {
                        "id": "4b2ef64b-b35d-4ea2-a6f2-4ef3cfb295f1",
                        "name": "Italo Chagas",
                        "email": "italo@auraxis.com.br",
                        "monthly_income_net": "5000.00",
                        "investor_profile": "conservador",
                    }
                },
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            404: json_error_response(
                description="Usuário não encontrado",
                message="Usuário não encontrado",
                error_code="NOT_FOUND",
                status_code=404,
            ),
        },
    )
    @jwt_required()
    def get(self) -> Response:
        user_or_response = self._authenticated_user_or_error()
        if isinstance(user_or_response, Response):
            return user_or_response
        user_data = _serialize_user_profile(user_or_response)
        return compat_success(
            legacy_payload={
                "message": "Perfil retornado com sucesso",
                "data": user_data,
            },
            status_code=200,
            message="Perfil retornado com sucesso",
            data={"user": user_data},
        )

    @doc(
        summary="Atualizar perfil do usuário",
        description=(
            "Atualiza o perfil do usuário autenticado.\n\n"
            "Campos aceitos:\n"
            "- gender: 'masculino', 'feminino', 'outro'\n"
            "- birth_date: 'YYYY-MM-DD'\n"
            "- monthly_income, net_worth, monthly_expenses, initial_investment,\n"
            "  monthly_investment: decimal\n"
            "- investment_goal_date: 'YYYY-MM-DD'\n"
            "- investor_profile: 'conservador', 'explorador', 'entusiasta'\n\n"
            "Exemplo de request:\n"
            "{\n"
            "  'gender': 'masculino',\n"
            "  'birth_date': '1990-05-15',\n"
            "  'monthly_income': '5000.00',\n"
            "  'net_worth': '100000.00',\n"
            "  'monthly_expenses': '2000.00',\n"
            "  'initial_investment': '10000.00',\n"
            "  'monthly_investment': '500.00',\n"
            "  'investment_goal_date': '2025-12-31',\n"
            "  'investor_profile': 'conservador'\n"
            "}\n\n"
            "Exemplo de resposta:\n"
            "{ 'message': 'Perfil atualizado com sucesso', "
            "'data': { ...dados do usuário... } }"
        ),
        tags=["Usuário"],
        security=[{"BearerAuth": []}],
        params=contract_header_param(supported_version="v2"),
        requestBody=json_request_body(
            schema=UserProfileSchema,
            description="Campos parciais do perfil financeiro e investidor.",
            example={
                "gender": "masculino",
                "birth_date": "1990-05-15",
                "monthly_income_net": "5000.00",
                "monthly_expenses": "2000.00",
                "net_worth": "100000.00",
                "investor_profile": "conservador",
                "state_uf": "SP",
                "occupation": "Founder",
            },
        ),
        responses={
            200: json_success_response(
                description="Perfil atualizado com sucesso",
                message="Perfil atualizado com sucesso",
                data_example={
                    "user": {
                        "id": "4b2ef64b-b35d-4ea2-a6f2-4ef3cfb295f1",
                        "monthly_income_net": "5000.00",
                        "monthly_expenses": "2000.00",
                        "investor_profile": "conservador",
                    }
                },
            ),
            400: json_error_response(
                description="Erro de validação",
                message="Erro de validação",
                error_code="VALIDATION_ERROR",
                status_code=400,
            ),
            401: json_error_response(
                description="Token revogado",
                message="Token revogado",
                error_code="UNAUTHORIZED",
                status_code=401,
            ),
            404: json_error_response(
                description="Usuário não encontrado",
                message="Usuário não encontrado",
                error_code="NOT_FOUND",
                status_code=404,
            ),
            500: json_error_response(
                description="Erro ao atualizar perfil",
                message="Erro ao atualizar perfil",
                error_code="INTERNAL_ERROR",
                status_code=500,
            ),
        },
    )
    @jwt_required()
    @use_kwargs(UserProfileSchema(), location="json")
    def put(self, **kwargs: Any) -> Response:
        user_or_response = self._authenticated_user_or_error()
        if isinstance(user_or_response, Response):
            return user_or_response
        user = user_or_response

        data = kwargs
        before_snapshot = _serialize_user_profile(user)

        result = update_user_profile(user, data)
        if result["error"]:
            return compat_error(
                legacy_payload={"message": result["error"]},
                status_code=400,
                message=str(result["error"]),
                error_code="VALIDATION_ERROR",
            )

        errors = user.validate_profile_data()
        if errors:
            return compat_error(
                legacy_payload={"message": "Erro de validação", "errors": errors},
                status_code=400,
                message="Erro de validação",
                error_code="VALIDATION_ERROR",
                details={"errors": errors},
            )

        try:
            db.session.commit()
            user_data = _serialize_user_profile(user)
            self._emit_profile_update_audit(
                user_id=str(user.id),
                before=before_snapshot,
                after=user_data,
                incoming_fields=tuple(data.keys()),
            )
            return compat_success(
                legacy_payload={
                    "message": "Perfil atualizado com sucesso",
                    "data": user_data,
                },
                status_code=200,
                message="Perfil atualizado com sucesso",
                data={"user": user_data},
            )
        except Exception:
            current_app.logger.exception("Erro ao atualizar perfil do usuário.")
            return compat_error(
                legacy_payload={"message": "Erro ao atualizar perfil"},
                status_code=500,
                message="Erro ao atualizar perfil",
                error_code="INTERNAL_ERROR",
            )

    @staticmethod
    def _emit_profile_update_audit(
        *,
        user_id: str,
        before: dict[str, Any],
        after: dict[str, Any],
        incoming_fields: tuple[str, ...],
    ) -> None:
        changed_fields = sorted(
            {
                field
                for field in incoming_fields
                if before.get(field) != after.get(field)
                or (
                    field == "monthly_income"
                    and before.get("monthly_income_net")
                    != after.get("monthly_income_net")
                )
                or (
                    field == "monthly_income_net"
                    and before.get("monthly_income") != after.get("monthly_income")
                )
            }
        )
        current_app.logger.info(
            "event=user.profile_update user_id=%s changed_fields=%s "
            "request_id=%s status=%s",
            user_id,
            ",".join(changed_fields),
            current_request_id(),
            200,
        )

    @staticmethod
    def _authenticated_user_or_error() -> Any:
        auth_context = get_active_auth_context()
        dependencies = get_user_dependencies()
        user = dependencies.get_user_by_id(UUID(auth_context.subject))
        if not user:
            return compat_error(
                legacy_payload={"message": "Usuário não encontrado"},
                status_code=404,
                message="Usuário não encontrado",
                error_code="NOT_FOUND",
            )

        if (
            auth_context.jti is None
            or not hasattr(user, "current_jti")
            or user.current_jti != auth_context.jti
        ):
            return compat_error(
                legacy_payload={"message": "Token revogado"},
                status_code=401,
                message="Token revogado",
                error_code="UNAUTHORIZED",
            )
        return user
