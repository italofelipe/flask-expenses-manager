from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Callable, cast
from uuid import UUID, uuid4

from dateutil.relativedelta import relativedelta

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.transaction_analytics_service import TransactionAnalyticsService
from app.services.transaction_reference_authorization_service import (
    TransactionReferenceAuthorizationError,
    enforce_transaction_reference_ownership,
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
    ) -> dict[str, Any]:
        transaction = cast(
            Transaction | None,
            Transaction.query.filter_by(id=transaction_id, deleted=False).first(),
        )
        if transaction is None:
            raise TransactionApplicationError(
                message="Transação não encontrada.",
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

        if normalized.get("status", "").lower() == "paid" and not normalized.get(
            "paid_at"
        ):
            raise _validation_error(
                "É obrigatório informar 'paid_at' ao marcar a transação "
                "como paga (status=PAID)."
            )
        if normalized.get("paid_at") and normalized.get("status", "").lower() != "paid":
            raise _validation_error(
                "'paid_at' só pode ser definido se o status for 'PAID'."
            )
        if "paid_at" in normalized and normalized["paid_at"] is not None:
            paid_at = self._coerce_datetime(normalized["paid_at"], field_name="paid_at")
            if paid_at > utc_now_compatible_with(paid_at):
                raise _validation_error("'paid_at' não pode ser uma data futura.")
            normalized["paid_at"] = paid_at

        due_date = self._coerce_date(
            normalized.get("due_date", transaction.due_date),
            field_name="due_date",
            required=True,
        )
        start_date = self._coerce_date(
            normalized.get("start_date", transaction.start_date),
            field_name="start_date",
            required=False,
        )
        end_date = self._coerce_date(
            normalized.get("end_date", transaction.end_date),
            field_name="end_date",
            required=False,
        )
        recurring_error = _validate_recurring_payload(
            is_recurring=bool(normalized.get("is_recurring", transaction.is_recurring)),
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
                message="Transação não encontrada.",
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
        except Exception:
            db.session.rollback()
            raise

    def get_month_summary(
        self,
        *,
        month: str,
        page: int,
        page_size: int,
    ) -> dict[str, Any]:
        year, month_number, normalized_month = _parse_month(month)
        analytics = self._analytics_service_factory(self._user_id)
        transactions = analytics.get_month_transactions(
            year=year, month_number=month_number
        )
        aggregates = analytics.get_month_aggregates(
            year=year, month_number=month_number
        )

        serialized = [_serialize_transaction(item) for item in transactions]
        paginated = PaginatedResponse.format(
            serialized, len(transactions), page, page_size
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


def _validate_recurring_payload(
    *,
    is_recurring: bool,
    due_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> str | None:
    if not is_recurring:
        if start_date and end_date and start_date > end_date:
            return "Parâmetro 'start_date' não pode ser maior que 'end_date'."
        return None

    if not start_date or not end_date:
        return (
            "Transações recorrentes exigem 'start_date' e 'end_date' "
            "no formato YYYY-MM-DD."
        )

    if start_date > end_date:
        return "Parâmetro 'start_date' não pode ser maior que 'end_date'."

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


def _serialize_transaction(transaction: Transaction) -> dict[str, Any]:
    return {
        "id": str(transaction.id),
        "title": transaction.title,
        "amount": str(transaction.amount),
        "type": transaction.type.value,
        "due_date": transaction.due_date.isoformat(),
        "start_date": (
            transaction.start_date.isoformat() if transaction.start_date else None
        ),
        "end_date": transaction.end_date.isoformat() if transaction.end_date else None,
        "description": transaction.description,
        "observation": transaction.observation,
        "is_recurring": transaction.is_recurring,
        "is_installment": transaction.is_installment,
        "installment_count": transaction.installment_count,
        "tag_id": str(transaction.tag_id) if transaction.tag_id else None,
        "account_id": str(transaction.account_id) if transaction.account_id else None,
        "credit_card_id": (
            str(transaction.credit_card_id) if transaction.credit_card_id else None
        ),
        "status": transaction.status.value,
        "currency": transaction.currency,
        "created_at": (
            transaction.created_at.isoformat() if transaction.created_at else None
        ),
        "updated_at": (
            transaction.updated_at.isoformat() if transaction.updated_at else None
        ),
    }
