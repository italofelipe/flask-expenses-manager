from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from app.extensions.database import db
from app.models.transaction import Transaction


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


@dataclass(frozen=True)
class RecurrenceWindow:
    start: date
    end: date


class RecurrenceService:
    @staticmethod
    def _build_window(
        transaction: Transaction, reference_date: date
    ) -> RecurrenceWindow | None:
        if (
            not transaction.is_recurring
            or transaction.deleted
            or transaction.is_installment
            or transaction.start_date is None
            or transaction.end_date is None
        ):
            return None

        if transaction.start_date > transaction.end_date:
            return None

        window_end = min(transaction.end_date, reference_date)
        if window_end < transaction.start_date:
            return None

        return RecurrenceWindow(start=transaction.start_date, end=window_end)

    @staticmethod
    def _iter_expected_due_dates(
        *,
        window: RecurrenceWindow,
        base_due_date: date,
    ) -> Iterable[date]:
        due_date = base_due_date
        while due_date < window.start:
            due_date = _add_months(due_date, 1)

        while due_date <= window.end:
            yield due_date
            due_date = _add_months(due_date, 1)

    @staticmethod
    def generate_missing_occurrences(reference_date: date | None = None) -> int:
        reference = reference_date or date.today()
        templates = Transaction.query.filter_by(
            is_recurring=True,
            deleted=False,
        ).all()

        created: list[Transaction] = []
        for template in templates:
            window = RecurrenceService._build_window(template, reference)
            if window is None:
                continue

            expected_dates = RecurrenceService._iter_expected_due_dates(
                window=window,
                base_due_date=template.due_date,
            )
            for due in expected_dates:
                if due == template.due_date:
                    continue

                exists = Transaction.query.filter_by(
                    user_id=template.user_id,
                    title=template.title,
                    amount=template.amount,
                    type=template.type,
                    due_date=due,
                    is_recurring=True,
                    start_date=template.start_date,
                    end_date=template.end_date,
                    deleted=False,
                ).first()
                if exists:
                    continue

                created.append(
                    Transaction(
                        user_id=template.user_id,
                        title=template.title,
                        description=template.description,
                        observation=template.observation,
                        is_recurring=True,
                        is_installment=False,
                        installment_count=None,
                        amount=template.amount,
                        currency=template.currency,
                        status=template.status,
                        type=template.type,
                        due_date=due,
                        start_date=template.start_date,
                        end_date=template.end_date,
                        tag_id=template.tag_id,
                        account_id=template.account_id,
                        credit_card_id=template.credit_card_id,
                        installment_group_id=(
                            template.installment_group_id or template.id
                        ),
                        paid_at=None,
                    )
                )

        if not created:
            return 0

        db.session.add_all(created)
        db.session.commit()
        return len(created)
