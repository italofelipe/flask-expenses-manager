from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, cast
from uuid import UUID

from app.extensions.database import db
from app.models.investment_operation import InvestmentOperation
from app.models.wallet import Wallet
from app.schemas.investment_operation_schema import InvestmentOperationSchema


@dataclass
class InvestmentOperationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class InvestmentOperationService:
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        self._schema = InvestmentOperationSchema()
        self._partial_schema = InvestmentOperationSchema(partial=True)

    def get_owned_investment(self, investment_id: UUID) -> Wallet:
        investment: Wallet | None = cast(
            Wallet | None, Wallet.query.filter_by(id=investment_id).first()
        )
        if not investment:
            raise InvestmentOperationError(
                message="Investimento não encontrado",
                code="NOT_FOUND",
                status_code=404,
            )
        if str(investment.user_id) != str(self.user_id):
            raise InvestmentOperationError(
                message="Você não tem permissão para acessar este investimento.",
                code="FORBIDDEN",
                status_code=403,
            )
        return investment

    def get_owned_operation(
        self, investment_id: UUID, operation_id: UUID
    ) -> InvestmentOperation:
        self.get_owned_investment(investment_id)
        operation: InvestmentOperation | None = cast(
            InvestmentOperation | None,
            InvestmentOperation.query.filter_by(
                id=operation_id, wallet_id=investment_id, user_id=self.user_id
            ).first(),
        )
        if not operation:
            raise InvestmentOperationError(
                message="Operação não encontrada",
                code="NOT_FOUND",
                status_code=404,
            )
        return operation

    def create_operation(
        self, investment_id: UUID, payload: dict[str, Any]
    ) -> InvestmentOperation:
        investment = self.get_owned_investment(investment_id)
        try:
            validated_data = self._schema.load(payload)
        except Exception as exc:
            raise InvestmentOperationError(
                message="Dados inválidos",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": getattr(exc, "messages", str(exc))},
            ) from exc

        operation = InvestmentOperation(
            wallet_id=investment.id,
            user_id=self.user_id,
            operation_type=str(validated_data["operation_type"]).lower(),
            quantity=validated_data["quantity"],
            unit_price=validated_data["unit_price"],
            fees=validated_data.get("fees"),
            executed_at=validated_data["executed_at"],
            notes=validated_data.get("notes"),
        )
        db.session.add(operation)
        db.session.commit()
        return operation

    def list_operations(
        self, investment_id: UUID, page: int, per_page: int
    ) -> tuple[list[InvestmentOperation], dict[str, int]]:
        self.get_owned_investment(investment_id)
        pagination = (
            InvestmentOperation.query.filter_by(
                wallet_id=investment_id, user_id=self.user_id
            )
            .order_by(
                InvestmentOperation.executed_at.desc(),
                InvestmentOperation.created_at.desc(),
            )
            .paginate(page=page, per_page=per_page, error_out=False)
        )
        meta = {
            "total": pagination.total,
            "page": pagination.page,
            "per_page": pagination.per_page,
            "pages": pagination.pages,
        }
        return pagination.items, meta

    def update_operation(
        self, investment_id: UUID, operation_id: UUID, payload: dict[str, Any]
    ) -> InvestmentOperation:
        operation = self.get_owned_operation(investment_id, operation_id)
        try:
            validated_data = self._partial_schema.load(payload, partial=True)
        except Exception as exc:
            raise InvestmentOperationError(
                message="Dados inválidos",
                code="VALIDATION_ERROR",
                status_code=400,
                details={"messages": getattr(exc, "messages", str(exc))},
            ) from exc

        for field, value in validated_data.items():
            if field == "operation_type" and value is not None:
                setattr(operation, field, str(value).lower())
            else:
                setattr(operation, field, value)
        db.session.commit()
        return operation

    def delete_operation(self, investment_id: UUID, operation_id: UUID) -> None:
        operation = self.get_owned_operation(investment_id, operation_id)
        db.session.delete(operation)
        db.session.commit()

    def get_summary(self, investment_id: UUID) -> dict[str, Any]:
        self.get_owned_investment(investment_id)
        operations = self._get_operations_for_investment(investment_id)

        buy_ops = [op for op in operations if op.operation_type == "buy"]
        sell_ops = [op for op in operations if op.operation_type == "sell"]

        buy_quantity = sum((Decimal(op.quantity) for op in buy_ops), Decimal("0"))
        sell_quantity = sum((Decimal(op.quantity) for op in sell_ops), Decimal("0"))
        net_quantity = buy_quantity - sell_quantity

        gross_buy_amount = sum(
            (Decimal(op.quantity) * Decimal(op.unit_price) for op in buy_ops),
            Decimal("0"),
        )
        gross_sell_amount = sum(
            (Decimal(op.quantity) * Decimal(op.unit_price) for op in sell_ops),
            Decimal("0"),
        )
        total_fees = sum((Decimal(op.fees or 0) for op in operations), Decimal("0"))

        average_buy_price = (
            (gross_buy_amount / buy_quantity) if buy_quantity > 0 else Decimal("0")
        )

        return {
            "total_operations": len(operations),
            "buy_operations": len(buy_ops),
            "sell_operations": len(sell_ops),
            "buy_quantity": str(buy_quantity),
            "sell_quantity": str(sell_quantity),
            "net_quantity": str(net_quantity),
            "gross_buy_amount": str(gross_buy_amount),
            "gross_sell_amount": str(gross_sell_amount),
            "average_buy_price": str(average_buy_price),
            "total_fees": str(total_fees),
        }

    def get_position(self, investment_id: UUID) -> dict[str, Any]:
        self.get_owned_investment(investment_id)
        operations = self._get_operations_for_investment(
            investment_id, chronological=True
        )

        current_quantity = Decimal("0")
        current_cost_basis = Decimal("0")
        buy_operations = 0
        sell_operations = 0
        total_buy_quantity = Decimal("0")
        total_sell_quantity = Decimal("0")

        for operation in operations:
            quantity = Decimal(operation.quantity)
            unit_price = Decimal(operation.unit_price)
            fees = Decimal(operation.fees or 0)
            operation_total = (quantity * unit_price) + fees

            if operation.operation_type == "buy":
                buy_operations += 1
                total_buy_quantity += quantity
                current_quantity += quantity
                current_cost_basis += operation_total
                continue

            sell_operations += 1
            total_sell_quantity += quantity

            if current_quantity <= 0:
                current_quantity -= quantity
                continue

            quantity_to_reduce = min(quantity, current_quantity)
            average_cost_before_sell = current_cost_basis / current_quantity
            current_cost_basis -= average_cost_before_sell * quantity_to_reduce
            current_quantity -= quantity

            if current_quantity <= 0:
                current_quantity = Decimal("0")
                current_cost_basis = Decimal("0")

        average_cost = (
            (current_cost_basis / current_quantity)
            if current_quantity > 0
            else Decimal("0")
        )

        return {
            "total_operations": len(operations),
            "buy_operations": buy_operations,
            "sell_operations": sell_operations,
            "total_buy_quantity": str(total_buy_quantity),
            "total_sell_quantity": str(total_sell_quantity),
            "current_quantity": str(current_quantity),
            "current_cost_basis": str(current_cost_basis),
            "average_cost": str(average_cost),
        }

    def get_invested_amount_by_date(
        self, investment_id: UUID, operation_date: date
    ) -> dict[str, Any]:
        self.get_owned_investment(investment_id)
        operations = cast(
            list[InvestmentOperation],
            InvestmentOperation.query.filter_by(
                wallet_id=investment_id,
                user_id=self.user_id,
                executed_at=operation_date,
            ).all(),
        )

        buy_operations = [op for op in operations if op.operation_type == "buy"]
        sell_operations = [op for op in operations if op.operation_type == "sell"]

        buy_amount = sum(
            (
                (Decimal(op.quantity) * Decimal(op.unit_price)) + Decimal(op.fees or 0)
                for op in buy_operations
            ),
            Decimal("0"),
        )
        sell_amount = sum(
            (
                (Decimal(op.quantity) * Decimal(op.unit_price)) - Decimal(op.fees or 0)
                for op in sell_operations
            ),
            Decimal("0"),
        )
        net_invested = buy_amount - sell_amount

        return {
            "date": operation_date.isoformat(),
            "total_operations": len(operations),
            "buy_operations": len(buy_operations),
            "sell_operations": len(sell_operations),
            "buy_amount": str(buy_amount),
            "sell_amount": str(sell_amount),
            "net_invested_amount": str(net_invested),
        }

    def _get_operations_for_investment(
        self, investment_id: UUID, *, chronological: bool = False
    ) -> list[InvestmentOperation]:
        query = InvestmentOperation.query.filter_by(
            wallet_id=investment_id, user_id=self.user_id
        )
        if chronological:
            query = query.order_by(
                InvestmentOperation.executed_at.asc(),
                InvestmentOperation.created_at.asc(),
            )
        return cast(list[InvestmentOperation], query.all())

    @staticmethod
    def serialize(operation: InvestmentOperation) -> dict[str, Any]:
        return {
            "id": str(operation.id),
            "wallet_id": str(operation.wallet_id),
            "user_id": str(operation.user_id),
            "operation_type": operation.operation_type,
            "quantity": str(operation.quantity),
            "unit_price": str(operation.unit_price),
            "fees": str(operation.fees),
            "executed_at": operation.executed_at.isoformat(),
            "notes": operation.notes,
            "created_at": (
                operation.created_at.isoformat() if operation.created_at else None
            ),
            "updated_at": (
                operation.updated_at.isoformat() if operation.updated_at else None
            ),
        }
