"""Service layer for Simulation persistence (J7)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from marshmallow import ValidationError

from app.extensions.database import db
from app.models.simulation import Simulation
from app.schemas.simulation_schema import SimulationSchema


@dataclass
class SimulationServiceError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class SimulationService:
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        self._schema = SimulationSchema()

    def save_simulation(self, payload: dict[str, Any]) -> Simulation:
        try:
            validated = self._schema.load(payload)
        except ValidationError as exc:
            raise SimulationServiceError(
                message="Dados inválidos para simulação.",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": exc.messages},
            ) from exc

        sim = Simulation(
            user_id=self.user_id,
            saved=True,
            **validated,
        )
        db.session.add(sim)
        db.session.commit()
        return sim

    def list_simulations(
        self,
        *,
        page: int,
        per_page: int,
    ) -> tuple[list[Simulation], dict[str, int]]:
        paginated = (
            Simulation.query.filter_by(user_id=self.user_id, saved=True)
            .order_by(Simulation.created_at.desc())
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        pagination = {
            "page": paginated.page,
            "per_page": paginated.per_page,
            "total": paginated.total,
            "pages": paginated.pages,
        }
        return list(paginated.items), pagination

    def get_simulation(self, simulation_id: UUID) -> Simulation:
        sim: Simulation | None = Simulation.query.filter_by(
            id=simulation_id, user_id=self.user_id
        ).first()
        if sim is None:
            raise SimulationServiceError(
                message="Simulação não encontrada.",
                code="NOT_FOUND",
                status_code=404,
            )
        return sim

    def delete_simulation(self, simulation_id: UUID) -> None:
        sim = self.get_simulation(simulation_id)
        db.session.delete(sim)
        db.session.commit()

    def serialize(self, sim: Simulation) -> dict[str, Any]:
        return dict(self._schema.dump(sim))
