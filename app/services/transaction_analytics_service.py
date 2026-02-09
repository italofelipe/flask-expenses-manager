from typing import Any, cast
from uuid import UUID

from sqlalchemy import case, func

from app.extensions.database import db
from app.models.tag import Tag
from app.models.transaction import Transaction, TransactionType


class TransactionAnalyticsService:
    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id

    def _month_query(self, *, year: int, month_number: int) -> Any:
        return (
            Transaction.query.filter_by(user_id=self.user_id, deleted=False)
            .filter(db.extract("year", Transaction.due_date) == year)
            .filter(db.extract("month", Transaction.due_date) == month_number)
        )

    def get_month_transactions(
        self, *, year: int, month_number: int
    ) -> list[Transaction]:
        transactions = self._month_query(year=year, month_number=month_number).all()
        return cast(list[Transaction], transactions)

    def get_month_aggregates(self, *, year: int, month_number: int) -> dict[str, Any]:
        row = (
            db.session.query(
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type == TransactionType.INCOME,
                                Transaction.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("income_total"),
                func.coalesce(
                    func.sum(
                        case(
                            (
                                Transaction.type == TransactionType.EXPENSE,
                                Transaction.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("expense_total"),
                func.count(Transaction.id).label("total_transactions"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.INCOME, 1), else_=0)
                    ),
                    0,
                ).label("income_transactions"),
                func.coalesce(
                    func.sum(
                        case((Transaction.type == TransactionType.EXPENSE, 1), else_=0)
                    ),
                    0,
                ).label("expense_transactions"),
            )
            .filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(db.extract("year", Transaction.due_date) == year)
            .filter(db.extract("month", Transaction.due_date) == month_number)
            .one()
        )

        income_total = row.income_total or 0
        expense_total = row.expense_total or 0
        return {
            "income_total": income_total,
            "expense_total": expense_total,
            "balance": income_total - expense_total,
            "total_transactions": int(row.total_transactions or 0),
            "income_transactions": int(row.income_transactions or 0),
            "expense_transactions": int(row.expense_transactions or 0),
        }

    def get_status_counts(self, *, year: int, month_number: int) -> dict[str, int]:
        default_counts = {
            "paid": 0,
            "pending": 0,
            "cancelled": 0,
            "postponed": 0,
            "overdue": 0,
        }
        rows = (
            db.session.query(Transaction.status, func.count(Transaction.id))
            .filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(db.extract("year", Transaction.due_date) == year)
            .filter(db.extract("month", Transaction.due_date) == month_number)
            .group_by(Transaction.status)
            .all()
        )
        for status_enum, count in rows:
            default_counts[status_enum.value] = int(count)
        return default_counts

    def get_top_categories(
        self,
        *,
        year: int,
        month_number: int,
        transaction_type: TransactionType,
    ) -> list[dict[str, Any]]:
        rows = (
            db.session.query(
                Transaction.tag_id,
                Tag.name,
                func.coalesce(func.sum(Transaction.amount), 0).label("total_amount"),
                func.count(Transaction.id).label("transactions_count"),
            )
            .outerjoin(Tag, Tag.id == Transaction.tag_id)
            .filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(Transaction.type == transaction_type)
            .filter(db.extract("year", Transaction.due_date) == year)
            .filter(db.extract("month", Transaction.due_date) == month_number)
            .group_by(Transaction.tag_id, Tag.name)
            .order_by(func.sum(Transaction.amount).desc())
            .limit(5)
            .all()
        )

        return [
            {
                "tag_id": str(tag_id) if tag_id else None,
                "category_name": tag_name or "Sem categoria",
                "total_amount": float(total_amount),
                "transactions_count": int(transactions_count),
            }
            for tag_id, tag_name, total_amount, transactions_count in rows
        ]
