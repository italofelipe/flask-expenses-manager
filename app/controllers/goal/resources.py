# mypy: disable-error-code=misc

from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec import doc, use_kwargs
from flask_apispec.views import MethodResource
from flask_jwt_extended import get_jwt_identity, jwt_required
from marshmallow import fields

from app.application.services.goal_application_service import GoalApplicationError

from .contracts import compat_success, goal_application_error_response
from .dependencies import get_goal_dependencies


class GoalCollectionResource(MethodResource):
    @doc(
        description="Cria uma nova meta financeira do usuário autenticado.",
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Meta criada com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def post(self) -> Any:
        user_id = UUID(get_jwt_identity())
        payload = request.get_json() or {}
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            goal_data = service.create_goal(payload)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Meta criada com sucesso",
                "goal": goal_data,
            },
            status_code=201,
            message="Meta criada com sucesso",
            data={"goal": goal_data},
        )

    @doc(
        description="Lista metas do usuário autenticado com paginação e filtro.",
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        params={
            "page": {"in": "query", "type": "integer", "required": False},
            "per_page": {"in": "query", "type": "integer", "required": False},
            "status": {"in": "query", "type": "string", "required": False},
            "X-API-Contract": {
                "in": "header",
                "description": "Opcional. Envie 'v2' para o contrato padronizado.",
                "type": "string",
                "required": False,
            },
        },
        responses={
            200: {"description": "Lista paginada de metas"},
            400: {"description": "Parâmetros inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @use_kwargs(
        {
            "page": fields.Int(load_default=1, validate=lambda x: x > 0),
            "per_page": fields.Int(load_default=10, validate=lambda x: 0 < x <= 100),
            "status": fields.Str(load_default=None),
        },
        location="query",
    )
    @jwt_required()
    def get(
        self,
        page: int,
        per_page: int,
        status: str | None,
    ) -> Any:
        user_id = UUID(get_jwt_identity())
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            result = service.list_goals(
                page=page,
                per_page=per_page,
                status=status,
            )
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        items = result["items"]
        pagination = result["pagination"]
        return compat_success(
            legacy_payload={
                "items": items,
                **pagination,
            },
            status_code=200,
            message="Metas listadas com sucesso",
            data={"items": items},
            meta={"pagination": pagination},
        )


class GoalResource(MethodResource):
    @doc(
        description="Retorna uma meta específica do usuário autenticado.",
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        params={"goal_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Meta encontrada"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Meta não encontrada"},
        },
    )
    @jwt_required()
    def get(self, goal_id: UUID) -> Any:
        user_id = UUID(get_jwt_identity())
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            goal_data = service.get_goal(goal_id)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={"goal": goal_data},
            status_code=200,
            message="Meta retornada com sucesso",
            data={"goal": goal_data},
        )

    @doc(
        description="Atualiza uma meta específica do usuário autenticado.",
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        params={"goal_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Meta atualizada"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Meta não encontrada"},
        },
    )
    @jwt_required()
    def put(self, goal_id: UUID) -> Any:
        user_id = UUID(get_jwt_identity())
        payload = request.get_json() or {}
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            goal_data = service.update_goal(goal_id, payload)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Meta atualizada com sucesso",
                "goal": goal_data,
            },
            status_code=200,
            message="Meta atualizada com sucesso",
            data={"goal": goal_data},
        )

    @doc(
        description="Remove uma meta específica do usuário autenticado.",
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        params={"goal_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Meta removida"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Meta não encontrada"},
        },
    )
    @jwt_required()
    def delete(self, goal_id: UUID) -> Any:
        user_id = UUID(get_jwt_identity())
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            service.delete_goal(goal_id)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={"message": "Meta removida com sucesso"},
            status_code=200,
            message="Meta removida com sucesso",
            data={},
        )


class GoalPlanResource(MethodResource):
    @doc(
        description=(
            "Calcula o plano da meta considerando renda, despesas e "
            "capacidade de aporte do usuário."
        ),
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        params={"goal_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Planejamento calculado com sucesso"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Meta não encontrada"},
        },
    )
    @jwt_required()
    def get(self, goal_id: UUID) -> Any:
        user_id = UUID(get_jwt_identity())
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            result = service.get_goal_plan(goal_id)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "goal": result["goal"],
                "goal_plan": result["goal_plan"],
            },
            status_code=200,
            message="Planejamento da meta calculado com sucesso",
            data={
                "goal": result["goal"],
                "goal_plan": result["goal_plan"],
            },
        )


class GoalSimulationResource(MethodResource):
    @doc(
        description=(
            "Executa simulação de meta sem persistência (what-if), "
            "retornando projeção e recomendações acionáveis."
        ),
        tags=["Metas"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Simulação calculada com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def post(self) -> Any:
        payload = request.get_json() or {}
        user_id = UUID(get_jwt_identity())
        dependencies = get_goal_dependencies()
        service = dependencies.goal_application_service_factory(user_id)
        try:
            result = service.simulate_goal_plan(payload)
        except GoalApplicationError as exc:
            return goal_application_error_response(exc)

        return compat_success(
            legacy_payload={"goal_plan": result["goal_plan"]},
            status_code=200,
            message="Simulação da meta calculada com sucesso",
            data={"goal_plan": result["goal_plan"]},
        )
