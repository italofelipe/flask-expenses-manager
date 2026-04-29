from __future__ import annotations

from typing import Any
from uuid import UUID

from flask import request
from flask_apispec.views import MethodResource
from marshmallow import fields

from app.application.services.simulation_application_service import (
    SimulationApplicationError,
)
from app.auth import current_user_id
from app.controllers.response_contract import compat_error_response
from app.utils.typed_decorators import typed_doc as doc
from app.utils.typed_decorators import typed_jwt_required as jwt_required
from app.utils.typed_decorators import typed_use_kwargs as use_kwargs

from .contracts import compat_success, simulation_application_error_response
from .dependencies import get_simulation_dependencies

# Hard cap on the JSON body of POST /simulations.
# A full installment-vs-cash payload (the heaviest tool) is well under 6 KB,
# so 16 KB leaves comfortable headroom and blocks abusive payloads.
_SIMULATION_BODY_MAX_BYTES = 16 * 1024


def _body_too_large_response() -> Any:
    details = {"max_bytes": _SIMULATION_BODY_MAX_BYTES}
    return compat_error_response(
        legacy_payload={
            "message": "Corpo da requisição excede o limite permitido.",
            "error": "PAYLOAD_TOO_LARGE",
            "details": details,
        },
        status_code=413,
        message="Corpo da requisição excede o limite permitido.",
        error_code="PAYLOAD_TOO_LARGE",
        details=details,
    )


def _enforce_body_size_cap() -> Any | None:
    """Return a 413 response if the request body exceeds the simulation cap.

    Checks ``Content-Length`` first (cheap), then falls back to inspecting the
    raw body length when the header is absent or unreliable.
    """
    declared = request.content_length
    if declared is not None and declared > _SIMULATION_BODY_MAX_BYTES:
        return _body_too_large_response()
    body = request.get_data(cache=True, as_text=False)
    if len(body) > _SIMULATION_BODY_MAX_BYTES:
        return _body_too_large_response()
    return None


class SimulationCollectionResource(MethodResource):
    @doc(
        description="Persiste o resultado de uma simulação do usuário autenticado.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        responses={
            201: {"description": "Simulação salva com sucesso"},
            400: {"description": "Dados inválidos"},
            401: {"description": "Token inválido"},
        },
    )
    @jwt_required()
    def post(self) -> Any:
        oversized = _enforce_body_size_cap()
        if oversized is not None:
            return oversized
        user_id = current_user_id()
        payload = request.get_json() or {}
        dependencies = get_simulation_dependencies()
        service = dependencies.simulation_application_service_factory(user_id)
        try:
            sim_data = service.save_simulation(payload)
        except SimulationApplicationError as exc:
            return simulation_application_error_response(exc)

        return compat_success(
            legacy_payload={
                "message": "Simulação salva com sucesso",
                "simulation": sim_data,
            },
            status_code=201,
            message="Simulação salva com sucesso",
            data={"simulation": sim_data},
        )

    @doc(
        description="Lista simulações salvas do usuário autenticado (paginado).",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        params={
            "page": {"in": "query", "type": "integer", "required": False},
            "per_page": {"in": "query", "type": "integer", "required": False},
            "tool_id": {"in": "query", "type": "string", "required": False},
        },
        responses={
            200: {"description": "Lista de simulações"},
            401: {"description": "Token inválido"},
        },
    )
    @use_kwargs(
        {
            "page": fields.Int(load_default=1, validate=lambda x: x > 0),
            "per_page": fields.Int(load_default=20, validate=lambda x: 0 < x <= 100),
            "tool_id": fields.Str(load_default=None),
        },
        location="query",
    )
    @jwt_required()
    def get(self, page: int, per_page: int, tool_id: str | None) -> Any:
        user_id = current_user_id()
        dependencies = get_simulation_dependencies()
        service = dependencies.simulation_application_service_factory(user_id)
        try:
            result = service.list_simulations(
                page=page, per_page=per_page, tool_id=tool_id
            )
        except SimulationApplicationError as exc:
            return simulation_application_error_response(exc)

        items = result["items"]
        pagination = result["pagination"]
        return compat_success(
            legacy_payload={"items": items, **pagination},
            status_code=200,
            message="Simulações listadas com sucesso",
            data={"items": items},
            meta={"pagination": pagination},
        )


class SimulationResource(MethodResource):
    @doc(
        description="Retorna uma simulação específica do usuário autenticado.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        params={"simulation_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Simulação encontrada"},
            401: {"description": "Token inválido"},
            404: {"description": "Simulação não encontrada"},
        },
    )
    @jwt_required()
    def get(self, simulation_id: UUID) -> Any:
        user_id = current_user_id()
        dependencies = get_simulation_dependencies()
        service = dependencies.simulation_application_service_factory(user_id)
        try:
            sim_data = service.get_simulation(simulation_id)
        except SimulationApplicationError as exc:
            return simulation_application_error_response(exc)

        return compat_success(
            legacy_payload={"simulation": sim_data},
            status_code=200,
            message="Simulação retornada com sucesso",
            data={"simulation": sim_data},
        )

    @doc(
        description="Remove uma simulação específica do usuário autenticado.",
        tags=["Simulações"],
        security=[{"BearerAuth": []}],
        params={"simulation_id": {"in": "path", "type": "string", "required": True}},
        responses={
            200: {"description": "Simulação removida"},
            401: {"description": "Token inválido"},
            404: {"description": "Simulação não encontrada"},
        },
    )
    @jwt_required()
    def delete(self, simulation_id: UUID) -> Any:
        user_id = current_user_id()
        dependencies = get_simulation_dependencies()
        service = dependencies.simulation_application_service_factory(user_id)
        try:
            service.delete_simulation(simulation_id)
        except SimulationApplicationError as exc:
            return simulation_application_error_response(exc)

        return compat_success(
            legacy_payload={"message": "Simulação removida com sucesso"},
            status_code=200,
            message="Simulação removida com sucesso",
            data={},
        )
