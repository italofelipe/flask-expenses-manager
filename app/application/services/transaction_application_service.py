from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, cast
from uuid import UUID, uuid4

from dateutil.relativedelta import relativedelta
from sqlalchemy import case, func

from app.extensions.database import db
from app.models.credit_card import CreditCard
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.cache_service import get_cache_service
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.services.transaction_reference_authorization_service import (
    TransactionReferenceAuthorizationError,
    enforce_transaction_reference_ownership,
)
from app.services.transaction_serialization import (
    TransactionPayload,
    serialize_transaction_payload,
)
from app.utils.datetime_utils import utc_now_compatible_with
from app.utils.pagination import PaginatedResponse

_MUTABLE_TRANSACTION_FIELDS = frozenset(
    {
        "title",
        "description",
        "observation",
        "is_recurring",
        "is_installment",
        "installment_count",
        "amount",
        "currency",
        "status",
        "type",
        "due_date",
        "start_date",
        "end_date",
        "tag_id",
        "account_id",
        "credit_card_id",
        "paid_at",
    }
)
_TRANSACTION_NOT_FOUND_MESSAGE = "Transação não encontrada."
_START_END_DATE_REQUIRED_MESSAGE = (
    "Informe ao menos um parâmetro: 'start_date' ou 'end_date'."
)
_START_END_DATE_ORDER_MESSAGE = (
    "Parâmetro 'start_date' não pode ser maior que 'end_date'."
)


@dataclass(frozen=True)
class TransactionApplicationError(Exception):
    message: str
    code: str
    status_code: int
    details: dict[str, Any] | None = None


class TransactionApplicationService:
    def __init__(
        self,
        *,
        user_id: UUID,
        analytics_service_factory: Callable[[UUID], TransactionAnalyticsService],
    ) -> None:
        self._user_id = user_id
        self._analytics_service_factory = analytics_service_factory

    @classmethod
    def with_defaults(cls, user_id: UUID) -> TransactionApplicationService:
        return cls(
            user_id=user_id,
            analytics_service_factory=TransactionAnalyticsService,
        )

    def _invalidate_dashboard_cache(self) -> None:
        """Bust all dashboard overview cache entries for this user."""
        get_cache_service().invalidate_pattern(f"dashboard:overview:{self._user_id}:*")

    def create_transaction(  # noqa: C901
        self,
        payload: dict[str, Any],
        *,
        installment_amount_builder: Callable[[Decimal, int], list[Decimal]],
    ) -> dict[str, Any]:
        normalized = dict(payload)
        tx_type = self._normalize_transaction_type(normalized.get("type"))
        tx_status = self._normalize_transaction_status(normalized.get("status"))
        amount = self._normalize_decimal_amount(normalized.get("amount"))
        due_date = self._coerce_date(
            normalized.get("due_date"),
            field_name="due_date",
            required=True,
        )
        if due_date is None:
            raise _validation_error(
                "Parâmetro 'due_date' é obrigatório no formato YYYY-MM-DD."
            )
        start_date = self._coerce_date(
            normalized.get("start_date"),
            field_name="start_date",
            required=False,
        )
        end_date = self._coerce_date(
            normalized.get("end_date"),
            field_name="end_date",
            required=False,
        )

        recurring_error = _validate_recurring_payload(
            is_recurring=bool(normalized.get("is_recurring", False)),
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
        )
        if recurring_error:
            raise _validation_error(recurring_error)

        self._assert_owned_references(
            tag_id=normalized.get("tag_id"),
            account_id=normalized.get("account_id"),
            credit_card_id=normalized.get("credit_card_id"),
        )

        if normalized.get("is_installment") and normalized.get("installment_count"):
            count = _normalize_installment_count(normalized.get("installment_count"))
            try:
                group_id = uuid4()
                installment_amounts = installment_amount_builder(amount, count)
                title = str(normalized.get("title", "")).strip()
                transactions: list[Transaction] = []
                for idx in range(count):
                    month_due_date = due_date + relativedelta(months=idx)
                    transactions.append(
                        Transaction(
                            user_id=self._user_id,
                            title=f"{title} ({idx + 1}/{count})",
                            amount=installment_amounts[idx],
                            type=tx_type,
                            due_date=month_due_date,
                            start_date=start_date,
                            end_date=end_date,
                            description=normalized.get("description"),
                            observation=normalized.get("observation"),
                            is_recurring=bool(normalized.get("is_recurring", False)),
                            is_installment=True,
                            installment_count=count,
                            tag_id=normalized.get("tag_id"),
                            account_id=normalized.get("account_id"),
                            credit_card_id=normalized.get("credit_card_id"),
                            status=tx_status,
                            currency=self._normalize_currency(
                                normalized.get("currency")
                            ),
                            installment_group_id=group_id,
                        )
                    )

                db.session.add_all(transactions)
                db.session.commit()
            except TransactionApplicationError:
                raise
            except Exception:
                db.session.rollback()
                raise

            return {
                "message": "Transações parceladas criadas com sucesso",
                "items": [_serialize_transaction(item) for item in transactions],
                "legacy_key": "transactions",
            }

        try:
            transaction = Transaction(
                user_id=self._user_id,
                title=str(normalized.get("title", "")),
                amount=amount,
                type=tx_type,
                due_date=due_date,
                start_date=start_date,
                end_date=end_date,
                description=normalized.get("description"),
                observation=normalized.get("observation"),
                is_recurring=bool(normalized.get("is_recurring", False)),
                is_installment=bool(normalized.get("is_installment", False)),
                installment_count=normalized.get("installment_count"),
                tag_id=normalized.get("tag_id"),
                account_id=normalized.get("account_id"),
                credit_card_id=normalized.get("credit_card_id"),
                status=tx_status,
                currency=self._normalize_currency(normalized.get("currency")),
            )
            db.session.add(transaction)
            db.session.commit()
            self._invalidate_dashboard_cache()
        except TransactionApplicationError:
            raise
        except Exception:
            db.session.rollback()
            raise

        return {
            "message": "Transação criada com sucesso",
            "items": [_serialize_transaction(transaction)],
            "legacy_key": "transaction",
        }

    def update_transaction(  # noqa: C901
        self,
        transaction_id: UUID,
        payload: dict[str, Any],
    ) -> TransactionPayload:
        transaction = cast(
            Transaction | None,
            Transaction.query.filter_by(id=transaction_id, deleted=False).first(),
        )
        if transaction is None:
            raise TransactionApplicationError(
                message=_TRANSACTION_NOT_FOUND_MESSAGE,
                code="NOT_FOUND",
                status_code=404,
            )

        if str(transaction.user_id) != str(self._user_id):
            raise TransactionApplicationError(
                message="Você não tem permissão para editar esta transação.",
                code="FORBIDDEN",
                status_code=403,
            )

        normalized = dict(payload)
        if "type" in normalized and normalized["type"] is not None:
            normalized["type"] = self._normalize_transaction_type(
                normalized["type"]
            ).value
        if "status" in normalized and normalized["status"] is not None:
            normalized["status"] = self._normalize_transaction_status(
                normalized["status"]
            ).value

        self._normalize_paid_at_for_update(normalized)

        due_date = self._coerce_date(
            normalized.get("due_date", transaction.due_date),
            field_name="due_date",
            required=True,
        )
        effective_start_date = (
            normalized["start_date"]
            if "start_date" in normalized
            else transaction.start_date
        )
        effective_end_date = (
            normalized["end_date"] if "end_date" in normalized else transaction.end_date
        )
        start_date = self._coerce_date(
            effective_start_date,
            field_name="start_date",
            required=False,
        )
        end_date = self._coerce_date(
            effective_end_date,
            field_name="end_date",
            required=False,
        )
        effective_is_recurring = bool(
            normalized["is_recurring"]
            if "is_recurring" in normalized
            else transaction.is_recurring
        )
        recurring_error = _validate_recurring_payload(
            is_recurring=effective_is_recurring,
            due_date=due_date,
            start_date=start_date,
            end_date=end_date,
        )
        if recurring_error:
            raise _validation_error(recurring_error)

        self._assert_owned_references(
            tag_id=normalized.get("tag_id", transaction.tag_id),
            account_id=normalized.get("account_id", transaction.account_id),
            credit_card_id=normalized.get("credit_card_id", transaction.credit_card_id),
        )

        try:
            _apply_transaction_updates(transaction, normalized)
            db.session.commit()
            self._invalidate_dashboard_cache()
        except Exception:
            db.session.rollback()
            raise

        return _serialize_transaction(transaction)

    def delete_transaction(self, transaction_id: UUID) -> None:
        transaction = cast(
            Transaction | None,
            Transaction.query.filter_by(id=transaction_id, deleted=False).first(),
        )
        if transaction is None:
            raise TransactionApplicationError(
                message=_TRANSACTION_NOT_FOUND_MESSAGE,
                code="NOT_FOUND",
                status_code=404,
            )

        if str(transaction.user_id) != str(self._user_id):
            raise TransactionApplicationError(
                message="Você não tem permissão para deletar esta transação.",
                code="FORBIDDEN",
                status_code=403,
            )

        try:
            transaction.deleted = True
            db.session.commit()
            self._invalidate_dashboard_cache()
        except Exception:
            db.session.rollback()
            raise

    def get_transaction(self, transaction_id: UUID) -> TransactionPayload:
        transaction = cast(
            Transaction | None,
            Transaction.query.filter_by(id=transaction_id, deleted=False).first(),
        )
        if transaction is None:
            raise TransactionApplicationError(
                message=_TRANSACTION_NOT_FOUND_MESSAGE,
                code="NOT_FOUND",
                status_code=404,
            )

        if str(transaction.user_id) != str(self._user_id):
            raise TransactionApplicationError(
                message="Você não tem permissão para visualizar esta transação.",
                code="FORBIDDEN",
                status_code=403,
            )

        return _serialize_transaction(transaction)

    def get_active_transactions(
        self,
        *,
        page: int,
        per_page: int,
        transaction_type: str | None,
        status: str | None,
        start_date: date | None,
        end_date: date | None,
        tag_id: UUID | None,
        account_id: UUID | None,
        credit_card_id: UUID | None,
    ) -> dict[str, Any]:
        query = Transaction.query.filter_by(user_id=self._user_id, deleted=False)

        if transaction_type:
            query = query.filter(
                Transaction.type == self._normalize_transaction_type(transaction_type)
            )
        if status:
            query = query.filter(
                Transaction.status == self._normalize_transaction_status(status)
            )
        if start_date:
            query = query.filter(Transaction.due_date >= start_date)
        if end_date:
            query = query.filter(Transaction.due_date <= end_date)
        if tag_id:
            query = query.filter(Transaction.tag_id == tag_id)
        if account_id:
            query = query.filter(Transaction.account_id == account_id)
        if credit_card_id:
            query = query.filter(Transaction.credit_card_id == credit_card_id)

        total = query.count()
        pages = (total + per_page - 1) // per_page if total else 0
        transactions = (
            query.order_by(Transaction.due_date.desc(), Transaction.created_at.desc())
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )

        return {
            "items": [_serialize_transaction(item) for item in transactions],
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": pages,
            },
        }

    def get_month_summary(
        self,
        *,
        month: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        total_transactions, transactions = _resolve_month_summary_page(
            analytics=analytics,
            year=year,
            month_number=month_number,
            page=page,
            page_size=page_size,
        )
        serialized = [_serialize_transaction(item) for item in transactions]
        paginated = PaginatedResponse.format(
            serialized, total_transactions, page, page_size
        )
        return {
            "month": normalized_month,
            "income_total": float(aggregates["income_total"]),
            "expense_total": float(aggregates["expense_total"]),
            "paginated": paginated,
        }

    def get_month_dashboard(self, *, month: str) -> dict[str, Any]:
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )
        status_counts = analytics.get_status_counts(
            year=year, month_number=month_number
        )
        top_expense_categories = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.EXPENSE,
        )
        top_income_categories = analytics.get_top_categories(
            year=year,
            month_number=month_number,
            transaction_type=TransactionType.INCOME,
        )
        return {
            "month": normalized_month,
            "income_total": float(aggregates["income_total"]),
            "expense_total": float(aggregates["expense_total"]),
            "balance": float(aggregates["balance"]),
            "counts": {
                "total_transactions": aggregates["total_transactions"],
                "income_transactions": aggregates["income_transactions"],
                "expense_transactions": aggregates["expense_transactions"],
                "status": status_counts,
            },
            "top_expense_categories": top_expense_categories,
            "top_income_categories": top_income_categories,
        }

    def get_due_transactions(
        self,
        *,
        start_date: str | date | None,
        end_date: str | date | None,
        page: int,
        per_page: int,
        order_by: str = "overdue_first",
    ) -> dict[str, Any]:
        parsed_start_date = self._coerce_date(
            start_date,
            field_name="start_date",
            required=False,
        )
        parsed_end_date = self._coerce_date(
            end_date,
            field_name="end_date",
            required=False,
        )
        if not parsed_start_date and not parsed_end_date:
            raise _validation_error(_START_END_DATE_REQUIRED_MESSAGE)
        if (
            parsed_start_date
            and parsed_end_date
            and parsed_start_date > parsed_end_date
        ):
            raise _validation_error(_START_END_DATE_ORDER_MESSAGE)

        normalized_order = str(order_by or "overdue_first").strip().lower()
        order_clauses = _resolve_due_ordering(normalized_order)

        base_query = Transaction.query.filter_by(user_id=self._user_id, deleted=False)
        if parsed_start_date:
            base_query = base_query.filter(Transaction.due_date >= parsed_start_date)
        if parsed_end_date:
            base_query = base_query.filter(Transaction.due_date <= parsed_end_date)

        total_transactions = base_query.count()
        income_transactions = base_query.filter(
            Transaction.type == TransactionType.INCOME
        ).count()
        expense_transactions = base_query.filter(
            Transaction.type == TransactionType.EXPENSE
        ).count()
        pages = (
            (total_transactions + per_page - 1) // per_page if total_transactions else 0
        )

        transactions = (
            base_query.outerjoin(
                CreditCard, Transaction.credit_card_id == CreditCard.id
            )
            .order_by(*order_clauses)
            .offset((page - 1) * per_page)
            .limit(per_page)
            .all()
        )
        serialized_transactions = [
            _serialize_transaction(item) for item in transactions
        ]

        return {
            "items": serialized_transactions,
            "counts": {
                "total_transactions": total_transactions,
                "income_transactions": income_transactions,
                "expense_transactions": expense_transactions,
            },
            "pagination": {
                "total": total_transactions,
                "page": page,
                "per_page": per_page,
                "pages": pages,
            },
        }

    def _assert_owned_references(
        self,
        *,
        tag_id: UUID | None,
        account_id: UUID | None,
        credit_card_id: UUID | None,
    ) -> None:
        try:
            enforce_transaction_reference_ownership(
                user_id=self._user_id,
                tag_id=tag_id,
                account_id=account_id,
                credit_card_id=credit_card_id,
            )
        except TransactionReferenceAuthorizationError as exc:
            message = (
                str(exc.args[0]) if exc.args else "Referência inválida para transação."
            )
            raise _validation_error(message) from exc

    @staticmethod
    def _normalize_transaction_type(raw_value: Any) -> TransactionType:
        value = str(raw_value or "").strip().lower()
        try:
            return TransactionType(value)
        except ValueError as exc:
            raise _validation_error(
                "Parâmetro 'type' inválido. Use 'income' ou 'expense'."
            ) from exc

    @staticmethod
    def _normalize_transaction_status(raw_value: Any) -> TransactionStatus:
        value = str(raw_value or "pending").strip().lower()
        try:
            return TransactionStatus(value)
        except ValueError as exc:
            raise _validation_error(
                "Parâmetro 'status' inválido. "
                "Use paid, pending, cancelled, postponed ou overdue."
            ) from exc

    @staticmethod
    def _normalize_currency(raw_value: Any) -> str:
        value = str(raw_value or "BRL").strip().upper()
        if not value:
            return "BRL"
        return value

    @staticmethod
    def _normalize_decimal_amount(raw_value: Any) -> Decimal:
        try:
            return Decimal(str(raw_value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise _validation_error(
                "Parâmetro 'amount' inválido. Informe um valor numérico válido."
            ) from exc

    @staticmethod
    def _coerce_date(
        raw_value: Any,
        *,
        field_name: str,
        required: bool,
    ) -> date | None:
        if raw_value in (None, ""):
            if required:
                raise _validation_error(
                    f"Parâmetro '{field_name}' é obrigatório no formato YYYY-MM-DD."
                )
            return None
        if isinstance(raw_value, date):
            return raw_value
        if isinstance(raw_value, datetime):
            return raw_value.date()
        if isinstance(raw_value, str):
            try:
                return datetime.strptime(raw_value, "%Y-%m-%d").date()
            except ValueError as exc:
                raise _validation_error(
                    f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
                ) from exc
        raise _validation_error(
            f"Parâmetro '{field_name}' inválido. Use o formato YYYY-MM-DD."
        )

    @staticmethod
    def _coerce_datetime(raw_value: Any, *, field_name: str) -> datetime:
        if isinstance(raw_value, datetime):
            return raw_value
        if isinstance(raw_value, str):
            normalized = raw_value.replace("Z", "+00:00")
            try:
                return datetime.fromisoformat(normalized)
            except ValueError as exc:
                raise _validation_error(
                    f"Parâmetro '{field_name}' inválido. Use formato datetime ISO-8601."
                ) from exc
        raise _validation_error(
            f"Parâmetro '{field_name}' inválido. Use formato datetime ISO-8601."
        )

    def _normalize_paid_at_for_update(self, normalized: dict[str, Any]) -> None:
        status = str(normalized.get("status", "")).strip().lower()
        paid_at_value = normalized.get("paid_at")

        if status == "paid" and not paid_at_value:
            raise _validation_error(
                "É obrigatório informar 'paid_at' ao marcar a transação "
                "como paga (status=PAID)."
            )
        if paid_at_value and status != "paid":
            raise _validation_error(
                "'paid_at' só pode ser definido se o status for 'PAID'."
            )
        if "paid_at" not in normalized or paid_at_value is None:
            return

        parsed_paid_at = self._coerce_datetime(paid_at_value, field_name="paid_at")
        if parsed_paid_at > utc_now_compatible_with(parsed_paid_at):
            raise _validation_error("'paid_at' não pode ser uma data futura.")
        normalized["paid_at"] = parsed_paid_at


def _validation_error(message: str) -> TransactionApplicationError:
    return TransactionApplicationError(
        message=message,
        code="VALIDATION_ERROR",
        status_code=400,
    )


def _normalize_installment_count(raw_count: Any) -> int:
    try:
        count = int(raw_count)
    except (TypeError, ValueError) as exc:
        raise _validation_error("'installment_count' deve ser maior que zero.") from exc
    if count < 1:
        raise _validation_error("'installment_count' deve ser maior que zero.")
    return count


def _parse_month(value: str) -> tuple[int, int, str]:
    if not value:
        raise _validation_error("Parâmetro 'month' é obrigatório no formato YYYY-MM.")
    try:
        year, month_number = map(int, value.split("-"))
    except ValueError as exc:
        raise _validation_error("Formato de mês inválido. Use YYYY-MM.") from exc

    if month_number < 1 or month_number > 12:
        raise _validation_error("Formato de mês inválido. Use YYYY-MM.")

    return year, month_number, f"{year:04d}-{month_number:02d}"


def _resolve_due_ordering(order_by: str) -> list[Any]:
    today = date.today()
    title_order = func.lower(func.coalesce(Transaction.title, ""))
    card_order = func.lower(func.coalesce(CreditCard.name, ""))
    overdue_bucket = case((Transaction.due_date < today, 0), else_=1)
    upcoming_bucket = case((Transaction.due_date >= today, 0), else_=1)

    if order_by == "overdue_first":
        return [
            overdue_bucket.asc(),
            Transaction.due_date.asc(),
            title_order.asc(),
            card_order.asc(),
            Transaction.created_at.asc(),
        ]
    if order_by == "upcoming_first":
        return [
            upcoming_bucket.asc(),
            Transaction.due_date.asc(),
            title_order.asc(),
            card_order.asc(),
            Transaction.created_at.asc(),
        ]
    if order_by == "date":
        return [
            Transaction.due_date.asc(),
            title_order.asc(),
            card_order.asc(),
            Transaction.created_at.asc(),
        ]
    if order_by == "title":
        return [
            title_order.asc(),
            Transaction.due_date.asc(),
            card_order.asc(),
            Transaction.created_at.asc(),
        ]
    if order_by == "card":
        return [
            card_order.asc(),
            Transaction.due_date.asc(),
            title_order.asc(),
            Transaction.created_at.asc(),
        ]
    raise _validation_error(
        "Parâmetro 'order_by' inválido. "
        "Use overdue_first, upcoming_first, date, title ou card."
    )


def _validate_recurring_payload(
    *,
    is_recurring: bool,
    due_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> str | None:
    if not is_recurring:
        if start_date and end_date and start_date > end_date:
            return _START_END_DATE_ORDER_MESSAGE
        return None

    if not start_date or not end_date:
        return (
            "Transações recorrentes exigem 'start_date' e 'end_date' "
            "no formato YYYY-MM-DD."
        )

    if start_date > end_date:
        return _START_END_DATE_ORDER_MESSAGE

    if due_date is None:
        return "Transações recorrentes exigem 'due_date' no formato YYYY-MM-DD."

    if due_date < start_date or due_date > end_date:
        return "Parâmetro 'due_date' deve estar entre 'start_date' e 'end_date'."

    return None


def _apply_transaction_updates(
    transaction: Transaction, updates: dict[str, Any]
) -> None:
    for field, value in updates.items():
        if field not in _MUTABLE_TRANSACTION_FIELDS:
            continue
        if field == "type" and value is not None:
            setattr(transaction, field, TransactionType(str(value).lower()))
            continue
        if field == "status" and value is not None:
            setattr(transaction, field, TransactionStatus(str(value).lower()))
            continue
        setattr(transaction, field, value)


def _serialize_transaction(transaction: Transaction) -> TransactionPayload:
    return serialize_transaction_payload(transaction)


def _resolve_month_summary_page(
    *,
    analytics: TransactionAnalyticsService,
    year: int,
    month_number: int,
    page: int,
    page_size: int,
) -> tuple[int, list[Transaction]]:
    analytics_type = type(analytics)
    supports_paginated_path = (
        getattr(analytics_type, "get_month_transaction_count", None)
        is not TransactionAnalyticsService.get_month_transaction_count
        and getattr(analytics_type, "get_month_transactions_page", None)
        is not TransactionAnalyticsService.get_month_transactions_page
    )
    paginated_count = getattr(analytics, "get_month_transaction_count", None)
    paginated_page = getattr(analytics, "get_month_transactions_page", None)
    if (
        supports_paginated_path
        and callable(paginated_count)
        and callable(paginated_page)
    ):
        total_transactions = int(paginated_count(year=year, month_number=month_number))
        transactions = cast(
            list[Transaction],
            paginated_page(
                year=year,
                month_number=month_number,
                page=page,
                per_page=page_size,
            ),
        )
        return total_transactions, transactions

    transactions = analytics.get_month_transactions(
        year=year, month_number=month_number
    )
    start_index = max(0, (page - 1) * page_size)
    end_index = start_index + page_size
    return len(transactions), transactions[start_index:end_index]
