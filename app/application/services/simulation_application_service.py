"""Application service for Simulation persistence (J7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable
from uuid import UUID

from app.services.simulation_service import SimulationService, SimulationServiceError


@dataclass(frozen=True)
class SimulationApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


def _to_application_error(exc: SimulationServiceError) -> SimulationApplicationError:
    return SimulationApplicationError(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )


class SimulationApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID,
        simulation_service_factory: Callable[[UUID], SimulationService],
    ) -> None:
        self._user_id = user_id
        self._service = simulation_service_factory(user_id)

    @classmethod
    def with_defaults(cls, user_id: UUID) -> SimulationApplicationService:
        return cls(
            user_id=user_id,
            simulation_service_factory=SimulationService,
        )

    def save_simulation(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            sim = self._service.save_simulation(payload)
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
        return self._service.serialize(sim)

    def list_simulations(
        self,
        *,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        try:
            sims, pagination = self._service.list_simulations(
                page=page,
                per_page=per_page,
            )
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
        return {
            "items": [self._service.serialize(s) for s in sims],
            "pagination": pagination,
        }

    def get_simulation(self, simulation_id: UUID) -> dict[str, Any]:
        try:
            sim = self._service.get_simulation(simulation_id)
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
        return self._service.serialize(sim)

    def delete_simulation(self, simulation_id: UUID) -> None:
        try:
            self._service.delete_simulation(simulation_id)
        except SimulationServiceError as exc:
            raise _to_application_error(exc) from exc
