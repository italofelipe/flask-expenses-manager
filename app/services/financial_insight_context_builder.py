"""Period-aware financial context snapshots for AI insights.

The builder computes deterministic facts from internal transaction data before
any LLM call. It deliberately emits sanitized dictionaries instead of model
instances so prompts and audit logs do not receive user PII or raw IDs.
"""

from __future__ import annotations

import json
import logging
import os
import re
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import UUID

from app.models.budget import Budget
from app.models.credit_card import CreditCard
from app.models.goal import Goal
from app.models.transaction import (
    Transaction,
    TransactionStatus,
    TransactionType,
)
from app.services.credit_card_bill_service import compute_utilization

INSIGHT_DIMENSIONS: tuple[str, ...] = (
    "general",
    "transactions",
    "credit_cards",
    "goals",
    "budgets",
)
"""Closed enum of dimension labels assigned to each AI insight item.

Decided on 2026-05-17 (MVP-3 wiki): each insight item must declare which
surface it belongs to so contextual pages can filter, while the global
`/insights` hub renders all dimensions grouped.
"""

_SNAPSHOT_VERSION = "financial_insight_snapshot.v1"
_CURRENCY = "BRL"
_TIMEZONE = "America/Sao_Paulo"

# Hard cap on serialized snapshot size sent to the LLM (Sprint 5 obs-1).
# When exceeded, `truncate_snapshot()` reduces large lists deterministically
# while preserving the structural backbone (schema_version, current_period,
# comparisons). Override via AI_SNAPSHOT_MAX_BYTES env for cost experiments.
DEFAULT_MAX_SNAPSHOT_BYTES = 12 * 1024
MAX_SNAPSHOT_BYTES = int(
    os.getenv("AI_SNAPSHOT_MAX_BYTES", str(DEFAULT_MAX_SNAPSHOT_BYTES))
)

_log = logging.getLogger(__name__)
_MONEY_QUANT = Decimal("0.01")
_PERCENT_QUANT = Decimal("0.01")
_EMAIL_MASK = "[email]"
_MAX_EMAIL_TOKEN_LENGTH = 320
_EMAIL_LOCAL_SYMBOLS = "._%+-"
_EMAIL_DOMAIN_SYMBOLS = "-_"
_CPF_RE = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
_LONG_NUMBER_RE = re.compile(r"\b\d{8,}\b")


def _money(value: object) -> Decimal:
    try:
        return Decimal(str(value or "0")).quantize(_MONEY_QUANT)
    except (InvalidOperation, ValueError):
        return Decimal("0.00")


def _money_str(value: object) -> str:
    return f"{_money(value):.2f}"


def _percent_str(value: object) -> str:
    try:
        return f"{Decimal(str(value or '0')).quantize(_PERCENT_QUANT):.2f}"
    except (InvalidOperation, ValueError):
        return "0.00"


def _safe_pct(numerator: Decimal, denominator: Decimal) -> str:
    if denominator == 0:
        return "0.00"
    return _percent_str(numerator / denominator * Decimal("100"))


def _is_email_candidate_char(char: str) -> bool:
    return char.isalnum() or char == "@" or char in _EMAIL_LOCAL_SYMBOLS


def _is_email_local_char(char: str) -> bool:
    return char.isalnum() or char in _EMAIL_LOCAL_SYMBOLS


def _is_email_domain_char(char: str) -> bool:
    return char.isalnum() or char in _EMAIL_DOMAIN_SYMBOLS


def _strip_email_boundary_dots(token: str) -> tuple[str, str, str]:
    prefix = ""
    suffix = ""
    candidate = token

    while candidate.startswith("."):
        prefix += "."
        candidate = candidate[1:]
    while candidate.endswith("."):
        suffix = "." + suffix
        candidate = candidate[:-1]

    return prefix, candidate, suffix


def _looks_like_email(candidate: str) -> bool:
    if candidate.count("@") != 1:
        return False

    local_part, domain = candidate.split("@", 1)
    if (
        not local_part
        or not domain
        or len(local_part) > 64
        or len(domain) > 253
        or "." not in domain
        or local_part.startswith(".")
        or local_part.endswith(".")
    ):
        return False

    if not all(_is_email_local_char(char) for char in local_part):
        return False

    labels = domain.split(".")
    return all(
        label
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        and all(_is_email_domain_char(char) for char in label)
        for label in labels
    )


def _redact_email_token(token: str) -> str:
    prefix, candidate, suffix = _strip_email_boundary_dots(token)
    if "@" not in candidate:
        return token
    if len(candidate) > _MAX_EMAIL_TOKEN_LENGTH or candidate.count("@") > 1:
        return f"{prefix}{_EMAIL_MASK}{suffix}"
    if _looks_like_email(candidate):
        return f"{prefix}{_EMAIL_MASK}{suffix}"
    return token


def _redact_email_tokens(text: str) -> str:
    redacted: list[str] = []
    token_chars: list[str] = []

    for char in text:
        if _is_email_candidate_char(char):
            token_chars.append(char)
            continue

        if token_chars:
            redacted.append(_redact_email_token("".join(token_chars)))
            token_chars = []
        redacted.append(char)

    if token_chars:
        redacted.append(_redact_email_token("".join(token_chars)))

    return "".join(redacted)


def _sanitize_text(value: object, *, max_length: int = 120) -> str | None:
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    text = _redact_email_tokens(text)
    text = _CPF_RE.sub("[cpf]", text)
    text = _LONG_NUMBER_RE.sub("[number]", text)
    text = " ".join(text.split())
    if len(text) > max_length:
        return text[: max_length - 1].rstrip() + "..."
    return text


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", None)
    return str(enum_value if enum_value is not None else value)


def _same_day_previous_year(anchor_date: date) -> date | None:
    """Return the same calendar day a year before, or None when invalid (Feb 29)."""
    try:
        return anchor_date.replace(year=anchor_date.year - 1)
    except ValueError:
        return None


def _same_day_previous_month(anchor_date: date) -> date | None:
    previous_year = anchor_date.year
    previous_month = anchor_date.month - 1
    if previous_month == 0:
        previous_year -= 1
        previous_month = 12

    days_in_previous_month = monthrange(previous_year, previous_month)[1]
    if anchor_date.day > days_in_previous_month:
        return None
    return date(previous_year, previous_month, anchor_date.day)


def _month_bounds(anchor_date: date) -> tuple[date, date]:
    last_day = monthrange(anchor_date.year, anchor_date.month)[1]
    return date(anchor_date.year, anchor_date.month, 1), date(
        anchor_date.year,
        anchor_date.month,
        last_day,
    )


def _week_bounds(anchor_date: date) -> tuple[date, date]:
    start = anchor_date - timedelta(days=anchor_date.weekday())
    return start, start + timedelta(days=6)


def _date_period(start: date, end: date, label: str) -> dict[str, str]:
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "label": label,
    }


class FinancialInsightContextBuilder:
    """Build sanitized financial snapshots for daily, weekly and monthly insights."""

    def build_daily(self, *, user_id: UUID, anchor_date: date) -> dict[str, Any]:
        """Return a daily snapshot with extended temporal comparisons."""
        current = self._period_snapshot(
            user_id=user_id,
            start=anchor_date,
            end=anchor_date,
            label=anchor_date.isoformat(),
            period_type="daily",
            include_credit_cards=True,
        )
        yesterday = anchor_date - timedelta(days=1)
        previous_week = anchor_date - timedelta(days=7)
        same_day_previous_month = _same_day_previous_month(anchor_date)
        same_day_previous_year = _same_day_previous_year(anchor_date)
        month_start = date(anchor_date.year, anchor_date.month, 1)

        missing_comparisons: list[str] = []
        comparisons: dict[str, Any] = {
            "yesterday": self._comparison_snapshot(
                user_id=user_id,
                current=current,
                start=yesterday,
                end=yesterday,
                label=yesterday.isoformat(),
            ),
            "previous_week": self._comparison_snapshot(
                user_id=user_id,
                current=current,
                start=previous_week,
                end=previous_week,
                label=previous_week.isoformat(),
            ),
            "month_to_date": self._compact_period_snapshot(
                self._period_snapshot(
                    user_id=user_id,
                    start=month_start,
                    end=anchor_date,
                    label=f"{anchor_date:%Y-%m}-to-{anchor_date:%d}",
                    period_type="month_to_date",
                )
            ),
        }
        if same_day_previous_month is not None:
            comparisons["same_day_previous_month"] = self._comparison_snapshot(
                user_id=user_id,
                current=current,
                start=same_day_previous_month,
                end=same_day_previous_month,
                label=same_day_previous_month.isoformat(),
            )
        else:
            missing_comparisons.append("same_day_previous_month")

        if same_day_previous_year is not None:
            comparisons["same_day_previous_year"] = self._comparison_snapshot(
                user_id=user_id,
                current=current,
                start=same_day_previous_year,
                end=same_day_previous_year,
                label=same_day_previous_year.isoformat(),
            )
        else:
            missing_comparisons.append("same_day_previous_year")

        current["comparisons"] = comparisons
        current["data_quality"]["missing_comparison_periods"] = missing_comparisons
        return current

    def build_weekly(self, *, user_id: UUID, anchor_date: date) -> dict[str, Any]:
        """Return a weekly snapshot for the ISO week containing ``anchor_date``."""
        start, end = _week_bounds(anchor_date)
        current = self._period_snapshot(
            user_id=user_id,
            start=start,
            end=end,
            label=f"{anchor_date.isocalendar().year}-W{anchor_date.isocalendar().week:02d}",
            period_type="weekly",
            include_daily_series=True,
            include_credit_cards=True,
        )
        previous_start = start - timedelta(days=7)
        previous_end = start - timedelta(days=1)
        current["comparisons"] = {
            "previous_period": self._comparison_snapshot(
                user_id=user_id,
                current=current,
                start=previous_start,
                end=previous_end,
                label=(
                    f"{previous_start.isocalendar().year}-"
                    f"W{previous_start.isocalendar().week:02d}"
                ),
            )
        }
        return current

    def build_monthly(self, *, user_id: UUID, anchor_date: date) -> dict[str, Any]:
        """Return a monthly snapshot for the calendar month containing anchor."""
        start, end = _month_bounds(anchor_date)
        return self._period_snapshot(
            user_id=user_id,
            start=start,
            end=end,
            label=f"{anchor_date:%Y-%m}",
            period_type="monthly",
            include_daily_series=True,
            include_budgets=True,
            include_goals=True,
            include_credit_cards=True,
        )

    def _comparison_snapshot(
        self,
        *,
        user_id: UUID,
        current: dict[str, Any],
        start: date,
        end: date,
        label: str,
    ) -> dict[str, Any]:
        comparison = self._period_snapshot(
            user_id=user_id,
            start=start,
            end=end,
            label=label,
            period_type="comparison",
        )
        compact = self._compact_period_snapshot(comparison)
        compact["delta"] = self._delta(current["current_period"], comparison)
        return compact

    def _compact_period_snapshot(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        current_period = snapshot["current_period"]
        return {
            "period": snapshot["period"],
            "paid": current_period["paid"],
            "commitments": current_period["commitments"],
            "cancelled_transaction_count": current_period[
                "cancelled_transaction_count"
            ],
            "transaction_count": snapshot["transactions"]["included_count"],
            "data_quality": snapshot["data_quality"],
        }

    def _period_snapshot(
        self,
        *,
        user_id: UUID,
        start: date,
        end: date,
        label: str,
        period_type: str,
        include_daily_series: bool = False,
        include_budgets: bool = False,
        include_goals: bool = False,
        include_credit_cards: bool = False,
    ) -> dict[str, Any]:
        transactions = self._fetch_transactions(user_id=user_id, start=start, end=end)
        non_cancelled = [
            tx for tx in transactions if tx.status != TransactionStatus.CANCELLED
        ]
        paid = [tx for tx in non_cancelled if tx.status == TransactionStatus.PAID]

        current_period = self._current_period_summary(transactions)
        snapshot: dict[str, Any] = {
            "schema_version": _SNAPSHOT_VERSION,
            "period_type": period_type,
            "currency": _CURRENCY,
            "timezone": _TIMEZONE,
            "anchor_date": end.isoformat(),
            "period": _date_period(start, end, label),
            "current_period": current_period,
            "comparisons": {},
            "daily_series": self._daily_series(paid, start=start, end=end)
            if include_daily_series
            else [],
            "extremes": self._day_extremes(paid, start=start, end=end),
            "categories": {
                "top_expense_categories": self._top_expense_categories(paid)
            },
            "transactions": self._transactions_payload(non_cancelled),
            "budgets": self._budgets_payload(user_id=user_id, start=start, end=end)
            if include_budgets
            else [],
            "goals": self._goals_payload(user_id=user_id) if include_goals else [],
            "credit_cards": self._credit_cards_payload(user_id=user_id, anchor=end)
            if include_credit_cards
            else [],
            "data_quality": {
                "has_transactions": bool(non_cancelled),
                "missing_comparison_periods": [],
            },
        }
        return snapshot

    def _credit_cards_payload(
        self,
        *,
        user_id: UUID,
        anchor: date,
    ) -> list[dict[str, Any]]:
        """Sanitized list of cards with current-cycle utilization snapshot.

        Returns one entry per card belonging to the user. Cards without
        closing_day/due_day are skipped (utilization undefined). PII is
        never emitted — raw user_id / last_four_digits / external IDs stay
        out of the snapshot.
        """
        cards = (
            CreditCard.query.filter_by(user_id=user_id).order_by(CreditCard.name).all()
        )
        payload: list[dict[str, Any]] = []
        for card in cards:
            if card.closing_day is None or card.due_day is None:
                continue
            util = compute_utilization(card, today=anchor)
            payload.append(
                {
                    "name": _sanitize_text(card.name, max_length=60) or "Cartão",
                    "brand": _sanitize_text(card.brand, max_length=20) or None,
                    "bank": _sanitize_text(card.bank, max_length=60) or None,
                    "limit_amount": _money_str(util.limit_amount or 0)
                    if util.limit_amount is not None
                    else None,
                    "committed_amount": _money_str(util.committed_amount),
                    "available_amount": _money_str(util.available_amount or 0)
                    if util.available_amount is not None
                    else None,
                    "utilization_pct": util.utilization_pct,
                    "cycle": {
                        "start_date": util.cycle.start_date.isoformat(),
                        "end_date": util.cycle.end_date.isoformat(),
                        "due_date": util.cycle.due_date.isoformat(),
                        "status": util.cycle.status,
                    },
                }
            )
        return payload

    def _fetch_transactions(
        self,
        *,
        user_id: UUID,
        start: date,
        end: date,
    ) -> list[Transaction]:
        rows = (
            Transaction.query.filter(
                Transaction.user_id == user_id,
                Transaction.deleted.is_(False),
                Transaction.due_date >= start,
                Transaction.due_date <= end,
            )
            .order_by(Transaction.due_date.asc(), Transaction.created_at.asc())
            .all()
        )
        return cast(list[Transaction], rows)

    def _current_period_summary(
        self,
        transactions: list[Transaction],
    ) -> dict[str, Any]:
        paid = [tx for tx in transactions if tx.status == TransactionStatus.PAID]
        pending = [tx for tx in transactions if tx.status == TransactionStatus.PENDING]
        overdue = [tx for tx in transactions if tx.status == TransactionStatus.OVERDUE]
        cancelled_count = sum(
            1 for tx in transactions if tx.status == TransactionStatus.CANCELLED
        )

        paid_income = self._sum(paid, TransactionType.INCOME)
        paid_expense = self._sum(paid, TransactionType.EXPENSE)
        pending_expense = self._sum(pending, TransactionType.EXPENSE)
        overdue_expense = self._sum(overdue, TransactionType.EXPENSE)

        return {
            "paid": {
                "income_total": _money_str(paid_income),
                "expense_total": _money_str(paid_expense),
                "balance": _money_str(paid_income - paid_expense),
                "transaction_count": len(paid),
            },
            "commitments": {
                "pending_expense_total": _money_str(pending_expense),
                "overdue_expense_total": _money_str(overdue_expense),
                "transaction_count": len(pending) + len(overdue),
            },
            "cancelled_transaction_count": cancelled_count,
        }

    def _delta(
        self,
        current_period: dict[str, Any],
        comparison_snapshot: dict[str, Any],
    ) -> dict[str, str]:
        current_paid = current_period["paid"]
        comparison_paid = comparison_snapshot["current_period"]["paid"]
        income_delta = _money(current_paid["income_total"]) - _money(
            comparison_paid["income_total"]
        )
        expense_delta = _money(current_paid["expense_total"]) - _money(
            comparison_paid["expense_total"]
        )
        balance_delta = _money(current_paid["balance"]) - _money(
            comparison_paid["balance"]
        )

        return {
            "income_total": _money_str(income_delta),
            "income_pct": _safe_pct(
                income_delta, _money(comparison_paid["income_total"])
            ),
            "expense_total": _money_str(expense_delta),
            "expense_pct": _safe_pct(
                expense_delta,
                _money(comparison_paid["expense_total"]),
            ),
            "balance": _money_str(balance_delta),
            "balance_pct": _safe_pct(
                balance_delta,
                _money(comparison_paid["balance"]),
            ),
        }

    def _daily_series(
        self,
        transactions: list[Transaction],
        *,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        index: dict[date, dict[str, Decimal | int]] = {}
        cursor = start
        while cursor <= end:
            index[cursor] = {
                "income": Decimal("0.00"),
                "expense": Decimal("0.00"),
                "count": 0,
            }
            cursor += timedelta(days=1)

        for tx in transactions:
            day = cast(date, tx.due_date)
            entry = index.setdefault(
                day,
                {"income": Decimal("0.00"), "expense": Decimal("0.00"), "count": 0},
            )
            if tx.type == TransactionType.INCOME:
                entry["income"] = cast(Decimal, entry["income"]) + _money(tx.amount)
            elif tx.type == TransactionType.EXPENSE:
                entry["expense"] = cast(Decimal, entry["expense"]) + _money(tx.amount)
            entry["count"] = cast(int, entry["count"]) + 1

        series: list[dict[str, Any]] = []
        cursor = start
        while cursor <= end:
            entry = index[cursor]
            income = cast(Decimal, entry["income"])
            expense = cast(Decimal, entry["expense"])
            series.append(
                {
                    "date": cursor.isoformat(),
                    "income_total": _money_str(income),
                    "expense_total": _money_str(expense),
                    "balance": _money_str(income - expense),
                    "transaction_count": cast(int, entry["count"]),
                }
            )
            cursor += timedelta(days=1)
        return series

    def _day_extremes(
        self,
        transactions: list[Transaction],
        *,
        start: date,
        end: date,
    ) -> dict[str, dict[str, str] | None]:
        series = self._daily_series(transactions, start=start, end=end)
        expense_days = [
            (item["date"], _money(item["expense_total"]))
            for item in series
            if _money(item["expense_total"]) > 0
        ]
        income_days = [
            (item["date"], _money(item["income_total"]))
            for item in series
            if _money(item["income_total"]) > 0
        ]
        return {
            "max_expense_day": self._extreme_day(expense_days, highest=True),
            "min_expense_day_with_activity": self._extreme_day(
                expense_days,
                highest=False,
            ),
            "max_income_day": self._extreme_day(income_days, highest=True),
            "min_income_day_with_activity": self._extreme_day(
                income_days,
                highest=False,
            ),
        }

    def _extreme_day(
        self,
        days: list[tuple[str, Decimal]],
        *,
        highest: bool,
    ) -> dict[str, str] | None:
        if not days:
            return None
        day, amount = (
            max(days, key=lambda item: item[1])
            if highest
            else min(
                days,
                key=lambda item: item[1],
            )
        )
        return {"date": day, "amount": _money_str(amount)}

    def _top_expense_categories(
        self,
        transactions: list[Transaction],
    ) -> list[dict[str, str]]:
        totals: dict[str, Decimal] = {}
        for tx in transactions:
            if tx.type != TransactionType.EXPENSE or tx.category is None:
                continue
            category = _enum_value(tx.category)
            if category is None:
                continue
            totals[category] = totals.get(category, Decimal("0.00")) + _money(tx.amount)

        return [
            {"category": category, "total": _money_str(total)}
            for category, total in sorted(
                totals.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ]

    def _transactions_payload(
        self,
        transactions: list[Transaction],
        *,
        sample_limit: int = 20,
    ) -> dict[str, Any]:
        sorted_transactions = sorted(
            transactions,
            key=lambda tx: (tx.due_date, _money(tx.amount)),
        )
        return {
            "included_count": len(transactions),
            "sample": [
                self._serialize_transaction(tx)
                for tx in sorted_transactions[:sample_limit]
            ],
        }

    def _serialize_transaction(self, transaction: Transaction) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "date": transaction.due_date.isoformat(),
            "type": _enum_value(transaction.type),
            "status": _enum_value(transaction.status),
            "amount": _money_str(transaction.amount),
            "currency": transaction.currency or _CURRENCY,
            "title": _sanitize_text(transaction.title),
            "is_recurring": bool(transaction.is_recurring),
            "is_installment": bool(transaction.is_installment),
        }
        description = _sanitize_text(transaction.description)
        category = _enum_value(transaction.category)
        if description and description != payload["title"]:
            payload["description"] = description
        if category:
            payload["category"] = category
        return payload

    def _budgets_payload(
        self,
        *,
        user_id: UUID,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        rows = (
            Budget.query.filter(
                Budget.user_id == user_id,
                Budget.is_active.is_(True),
                Budget.period == "monthly",
            )
            .order_by(Budget.created_at.asc())
            .all()
        )
        budgets = cast(list[Budget], rows)
        paid = [
            tx
            for tx in self._fetch_transactions(user_id=user_id, start=start, end=end)
            if tx.status == TransactionStatus.PAID
            and tx.type == TransactionType.EXPENSE
        ]

        result: list[dict[str, Any]] = []
        for budget in budgets:
            category = str(budget.category) if budget.category else None
            spent = Decimal("0.00")
            for tx in paid:
                if category is None or _enum_value(tx.category) == category:
                    spent += _money(tx.amount)

            amount = _money(budget.amount)
            result.append(
                {
                    "name": _sanitize_text(budget.name) or "Orçamento",
                    "category": category,
                    "period": str(budget.period),
                    "amount": _money_str(amount),
                    "spent": _money_str(spent),
                    "utilization_pct": _safe_pct(spent, amount),
                    "exceeded": spent > amount,
                }
            )
        return result

    def _goals_payload(self, *, user_id: UUID) -> list[dict[str, Any]]:
        rows = (
            Goal.query.filter(
                Goal.user_id == user_id,
                Goal.status == "active",
            )
            .order_by(Goal.priority.asc(), Goal.created_at.asc())
            .all()
        )
        goals = cast(list[Goal], rows)

        result: list[dict[str, Any]] = []
        for goal in goals:
            current = _money(goal.current_amount)
            target = _money(goal.target_amount)
            result.append(
                {
                    "title": _sanitize_text(goal.title) or "Meta",
                    "current_amount": _money_str(current),
                    "target_amount": _money_str(target),
                    "progress_pct": _safe_pct(current, target),
                    "target_date": goal.target_date.isoformat()
                    if goal.target_date
                    else None,
                }
            )
        return result

    def _sum(
        self,
        transactions: list[Transaction],
        transaction_type: TransactionType,
    ) -> Decimal:
        return sum(
            (_money(tx.amount) for tx in transactions if tx.type == transaction_type),
            Decimal("0.00"),
        )


def _measure_snapshot_bytes(snapshot: dict[str, Any]) -> int:
    """Return UTF-8 byte size of the JSON-serialized snapshot."""
    return len(json.dumps(snapshot, ensure_ascii=False, sort_keys=True).encode("utf-8"))


def _trim_transactions(snapshot: dict[str, Any]) -> bool:
    txs = snapshot.get("transactions")
    if not isinstance(txs, dict):
        return False
    items = txs.get("items")
    if not (isinstance(items, list) and len(items) > 15):
        return False
    expenses = [i for i in items if i.get("type") == "expense"]
    incomes = [i for i in items if i.get("type") == "income"]
    kept = (
        sorted(expenses, key=lambda i: float(i.get("amount", 0) or 0), reverse=True)[
            :10
        ]
        + sorted(incomes, key=lambda i: float(i.get("amount", 0) or 0), reverse=True)[
            :5
        ]
    )
    snapshot["transactions"] = {**txs, "items": kept}
    return True


def _trim_daily_series(snapshot: dict[str, Any]) -> bool:
    series = snapshot.get("daily_series")
    if isinstance(series, list) and len(series) > 7:
        snapshot["daily_series"] = series[-7:]
        return True
    return False


def _trim_idle_credit_cards(snapshot: dict[str, Any]) -> bool:
    cards = snapshot.get("credit_cards")
    if not (isinstance(cards, list) and cards):
        return False
    active = [
        c
        for c in cards
        if isinstance(c, dict) and c.get("utilization_pct") not in (None, 0, 0.0)
    ]
    if len(active) < len(cards):
        snapshot["credit_cards"] = active
        return True
    return False


def _trim_top_categories(snapshot: dict[str, Any]) -> bool:
    categories = snapshot.get("categories")
    if not isinstance(categories, dict):
        return False
    top = categories.get("top_expense_categories")
    if isinstance(top, list) and len(top) > 5:
        snapshot["categories"] = {**categories, "top_expense_categories": top[:5]}
        return True
    return False


def truncate_snapshot(
    snapshot: dict[str, Any],
    *,
    max_bytes: int = MAX_SNAPSHOT_BYTES,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return ``(possibly_truncated, info)`` keeping the snapshot under max_bytes.

    Truncation order (least → most destructive):

    1. transactions: keep top 10 by expense amount, then top 5 income.
    2. daily_series: keep most recent 7 entries.
    3. credit_cards: drop entries with zero/None utilization_pct.
    4. categories.top_expense_categories: keep top 5.

    Always preserved: ``schema_version``, ``period_type``, ``period``,
    ``current_period``, ``comparisons``, ``data_quality``. Caller receives
    a dict describing what changed for observability.
    """
    original_bytes = _measure_snapshot_bytes(snapshot)
    info: dict[str, Any] = {
        "snapshot_bytes_original": original_bytes,
        "snapshot_bytes_final": original_bytes,
        "truncated": False,
        "dropped_sections": [],
        "max_bytes": max_bytes,
    }
    if original_bytes <= max_bytes:
        return snapshot, info

    truncated = dict(snapshot)
    dropped: list[str] = info["dropped_sections"]
    steps = (
        ("transactions.items", _trim_transactions),
        ("daily_series", _trim_daily_series),
        ("credit_cards.idle", _trim_idle_credit_cards),
        ("categories.top_expense_categories", _trim_top_categories),
    )
    for label, step in steps:
        if step(truncated):
            dropped.append(label)
        if _measure_snapshot_bytes(truncated) <= max_bytes:
            break

    final_bytes = _measure_snapshot_bytes(truncated)
    info["snapshot_bytes_final"] = final_bytes
    info["truncated"] = True
    _log.warning(
        "ai_advisory.snapshot.truncated original=%d final=%d dropped=%s",
        original_bytes,
        final_bytes,
        dropped,
    )
    return truncated, info


__all__ = [
    "FinancialInsightContextBuilder",
    "INSIGHT_DIMENSIONS",
    "MAX_SNAPSHOT_BYTES",
    "truncate_snapshot",
]
