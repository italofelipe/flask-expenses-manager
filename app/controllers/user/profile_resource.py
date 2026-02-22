# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import Response, current_app
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required

from app.application.services.user_profile_service import update_user_profile
from app.extensions.database import db
from app.schemas.user_schemas import UserProfileSchema

from .contracts import compat_error, compat_success
from .dependencies import get_user_dependencies
from .helpers import _serialize_user_profile


class UserProfileResource(MethodResource):
    @doc(
        description=(
            "Atualiza o perfil do usuário autenticado.\n\n"
            "Campos aceitos:\n"
            "- gender: 'masculino', 'feminino', 'outro'\n"
            "- birth_date: 'YYYY-MM-DD'\n"
            """- monthly_income, net_worth, monthly_expenses, initial_investment,
            monthly_investment: decimal\n"""
            "- investment_goal_date: 'YYYY-MM-DD'\n"
            "- investor_profile: 'conservador', 'explorador', 'entusiasta'\n\n"
            "Exemplo de request:\n"
            """{\n  'gender': 'masculino', 'birth_date': '1990-05-15',
            'monthly_income': '5000.00',
            'net_worth': '100000.00',
            'monthly_expenses': '2000.00',
            'initial_investment': '10000.00',
            'monthly_investment': '500.00',
            'investment_goal_date': '2025-12-31',
            'investor_profile': 'conservador' }\n\n"""
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
    )
    @jwt_required()
    @use_kwargs(UserProfileSchema(), location="json")
    def put(self, **kwargs: Any) -> Response:
        user_id = UUID(get_jwt_identity())
        jti = get_jwt()["jti"]
        dependencies = get_user_dependencies()
        user = dependencies.get_user_by_id(user_id)
        if not user:
            return compat_error(
                legacy_payload={"message": "Usuário não encontrado"},
                status_code=404,
                message="Usuário não encontrado",
                error_code="NOT_FOUND",
            )

        if not hasattr(user, "current_jti") or user.current_jti != jti:
            return compat_error(
                legacy_payload={"message": "Token revogado"},
                status_code=401,
                message="Token revogado",
                error_code="UNAUTHORIZED",
            )

        data = kwargs

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
