from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec.views import MethodResource

from app.auth import current_user_id
from app.services.budget_service import BudgetService, BudgetServiceError
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required

from .contracts import budget_service_error_response, compat_success


def _get_service() -> BudgetService:
    return BudgetService(current_user_id())


class BudgetCollectionResource(MethodResource):
    @doc(
        description=(
            "Lista todos os orçamentos ativos do usuário com valor gasto no período."
        ),
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Lista de orçamentos com gasto por período"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def get(self) -> Any:
        service = _get_service()
        budgets = service.list_budgets()
        items = [service.serialize_with_spent(b) for b in budgets]
        return compat_success(
            legacy_payload={"items": items},
            status_code=200,
            message="Orçamentos listados com sucesso",
            data={"items": items},
        )

    @doc(
        description="Cria um novo orçamento para o usuário autenticado.",
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Orçamento criado com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def post(self) -> Any:
        service = _get_service()
        payload = request.get_json() or {}
        try:
            budget = service.create_budget(payload)
        except BudgetServiceError as exc:
            return budget_service_error_response(exc)

        data = service.serialize_with_spent(budget)
        return compat_success(
            legacy_payload={"message": "Orçamento criado com sucesso", "budget": data},
            status_code=201,
            message="Orçamento criado com sucesso",
            data={"budget": data},
        )


class BudgetSummaryResource(MethodResource):
    @doc(
        description=(
            "Retorna total orçado vs total gasto no período atual (orçamentos ativos)."
        ),
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        responses={
            200: {"description": "Resumo de orçamentos vs gastos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def get(self) -> Any:
        service = _get_service()
        summary = service.get_summary()
        return compat_success(
            legacy_payload={"summary": summary},
            status_code=200,
            message="Resumo de orçamentos calculado com sucesso",
            data={"summary": summary},
        )


class BudgetResource(MethodResource):
    @doc(
        description=(
            "Retorna um orçamento específico do usuário com valor gasto no período."
        ),
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        params={"budget_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Orçamento encontrado"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Orçamento não encontrado"},
        },
    )
    @jwt_required()
    def get(self, budget_id: UUID) -> Any:
        service = _get_service()
        try:
            budget = service.get_budget(budget_id)
        except BudgetServiceError as exc:
            return budget_service_error_response(exc)

        data = service.serialize_with_spent(budget)
        return compat_success(
            legacy_payload={"budget": data},
            status_code=200,
            message="Orçamento retornado com sucesso",
            data={"budget": data},
        )

    @doc(
        description="Atualiza parcialmente um orçamento do usuário autenticado.",
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        params={"budget_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Orçamento atualizado"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Orçamento não encontrado"},
        },
    )
    @jwt_required()
    def patch(self, budget_id: UUID) -> Any:
        service = _get_service()
        payload = request.get_json() or {}
        try:
            budget = service.update_budget(budget_id, payload)
        except BudgetServiceError as exc:
            return budget_service_error_response(exc)

        data = service.serialize_with_spent(budget)
        return compat_success(
            legacy_payload={
                "message": "Orçamento atualizado com sucesso",
                "budget": data,
            },
            status_code=200,
            message="Orçamento atualizado com sucesso",
            data={"budget": data},
        )

    @doc(
        description="Remove um orçamento específico do usuário autenticado.",
        tags=["Orçamentos"],
        security=[{"BearerAuth": []}],
        params={"budget_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Orçamento removido"},
            401: {"description": "Token inválido"},
            403: {"description": "Sem permissão"},
            404: {"description": "Orçamento não encontrado"},
        },
    )
    @jwt_required()
    def delete(self, budget_id: UUID) -> Any:
        service = _get_service()
        try:
            service.delete_budget(budget_id)
        except BudgetServiceError as exc:
            return budget_service_error_response(exc)

        return compat_success(
            legacy_payload={"message": "Orçamento removido com sucesso"},
            status_code=200,
            message="Orçamento removido com sucesso",
            data={},
        )
