from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Callable
from uuid import UUID

from app.services.investment_operation_service import (
    InvestmentOperationError,
    InvestmentOperationService,
)


@dataclass(frozen=True)
class InvestmentApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class InvestmentApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID,
        investment_operation_service_factory: Callable[
            [UUID], InvestmentOperationService
        ],
    ) -> None:
        self._user_id = user_id
        self._investment_operation_service_factory = (
            investment_operation_service_factory
        )

    @classmethod
    def with_defaults(cls, user_id: UUID) -> InvestmentApplicationService:
        return cls(
            user_id=user_id,
            investment_operation_service_factory=InvestmentOperationService,
        )

    def create_operation(
        self,
        investment_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            operation = service.create_operation(investment_id, payload)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc
        return service.serialize(operation)

    def list_operations(
        self,
        investment_id: UUID,
        *,
        page: int,
        per_page: int,
    ) -> dict[str, Any]:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            operations, pagination = service.list_operations(
                investment_id, page, per_page
            )
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc
        return {
            "items": [service.serialize(item) for item in operations],
            "pagination": pagination,
        }

    def update_operation(
        self,
        investment_id: UUID,
        operation_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            operation = service.update_operation(investment_id, operation_id, payload)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc
        return service.serialize(operation)

    def delete_operation(self, investment_id: UUID, operation_id: UUID) -> None:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            service.delete_operation(investment_id, operation_id)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc

    def get_summary(self, investment_id: UUID) -> dict[str, Any]:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            return service.get_summary(investment_id)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc

    def get_position(self, investment_id: UUID) -> dict[str, Any]:
        service = self._investment_operation_service_factory(self._user_id)
        try:
            return service.get_position(investment_id)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc

    def get_invested_amount_by_date(
        self,
        investment_id: UUID,
        raw_date: str | date,
    ) -> dict[str, Any]:
        operation_date = _coerce_date(raw_date, field_name="date")
        service = self._investment_operation_service_factory(self._user_id)
        try:
            return service.get_invested_amount_by_date(investment_id, operation_date)
        except InvestmentOperationError as exc:
            raise _to_investment_application_error(exc) from exc


def _to_investment_application_error(
    exc: InvestmentOperationError,
) -> InvestmentApplicationError:
    return InvestmentApplicationError(
        message=exc.message,
        code=exc.code,
        status_code=exc.status_code,
        details=exc.details,
    )


def _coerce_date(raw_value: str | date, *, field_name: str) -> date:
    if isinstance(raw_value, date):
        return raw_value
    if isinstance(raw_value, str):
        if not raw_value:
            raise InvestmentApplicationError(
                message=f"Parâmetro '{field_name}' é obrigatório.",
                code="VALIDATION_ERROR",
                status_code=400,
            )
        try:
            return datetime.strptime(raw_value, "%Y-%m-%d").date()
        except ValueError as exc:
            raise InvestmentApplicationError(
                message=f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD.",
                code="VALIDATION_ERROR",
                status_code=400,
            ) from exc
    raise InvestmentApplicationError(
        message=f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD.",
        code="VALIDATION_ERROR",
        status_code=400,
    )
