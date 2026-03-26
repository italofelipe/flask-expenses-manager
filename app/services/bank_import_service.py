from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Sequence
from uuid import UUID

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.services.bank_statement_parsers import ParsedEntry, parse_nubank_csv, parse_ofx

_BANK_ALIASES = {
    "banco do brasil": "bb",
    "bb": "bb",
    "bradesco": "bradesco",
    "caixa": "caixa",
    "caixa economica federal": "caixa",
    "itau": "itau",
    "itaú": "itau",
    "nubank": "nubank",
}


@dataclass(frozen=True)
class BankImportPreviewEntry:
    external_id: str
    date: str
    description: str
    amount: Decimal
    transaction_type: str
    bank_name: str
    is_duplicate: bool
    duplicate_reason: str | None = None


@dataclass(frozen=True)
class BankImportPreview:
    bank_name: str
    entries: list[BankImportPreviewEntry]
    total_entries: int
    duplicate_entries: int
    new_entries: int


@dataclass(frozen=True)
class BankImportConfirmation:
    bank_name: str
    month: str
    imported_count: int
    skipped_duplicates: int
    replaced_count: int
    transactions: list[Transaction]


@dataclass(frozen=True)
class BankImportSelectedEntry:
    external_id: str
    date: date
    description: str
    amount: Decimal
    transaction_type: str
    bank_name: str


class BankImportService:
    def __init__(self, user_id: UUID | str) -> None:
        self.user_id = UUID(user_id) if isinstance(user_id, str) else user_id

    def build_preview(self, *, content: str, bank_name: str) -> BankImportPreview:
        normalized_bank = _normalize_bank_name(bank_name)
        if not content.strip():
            raise ValueError("Bank statement content cannot be empty")

        parsed_entries = _parse_entries(content=content, bank_name=normalized_bank)
        existing_external_ids = self._load_existing_external_ids(parsed_entries)

        preview_entries: list[BankImportPreviewEntry] = []
        duplicate_entries = 0
        seen_external_ids: set[str] = set()

        for entry in parsed_entries:
            duplicate_reason: str | None = None
            if entry.external_id in existing_external_ids:
                duplicate_reason = "existing_transaction"
            elif entry.external_id in seen_external_ids:
                duplicate_reason = "duplicate_in_file"

            if duplicate_reason is None:
                seen_external_ids.add(entry.external_id)
            else:
                duplicate_entries += 1

            preview_entries.append(
                BankImportPreviewEntry(
                    external_id=entry.external_id,
                    date=entry.date.isoformat(),
                    description=entry.description,
                    amount=entry.amount,
                    transaction_type=entry.transaction_type,
                    bank_name=entry.bank_name,
                    is_duplicate=duplicate_reason is not None,
                    duplicate_reason=duplicate_reason,
                )
            )

        return BankImportPreview(
            bank_name=normalized_bank,
            entries=preview_entries,
            total_entries=len(preview_entries),
            duplicate_entries=duplicate_entries,
            new_entries=len(preview_entries) - duplicate_entries,
        )

    def confirm_import(
        self,
        *,
        bank_name: str,
        month: str,
        mode: str,
        selected_entries: Sequence[dict[str, Any]],
    ) -> BankImportConfirmation:
        normalized_bank = _normalize_bank_name(bank_name)
        normalized_month = _normalize_month(month)
        normalized_mode = _normalize_mode(mode)
        entries = [
            _normalize_selected_entry(payload, expected_bank=normalized_bank)
            for payload in selected_entries
        ]

        if not entries:
            raise ValueError("At least one transaction must be selected")

        _validate_entries_month(entries, month=normalized_month)

        replaced_count = 0
        if normalized_mode == "replace_month":
            replaced_count = self._replace_month_transactions(
                bank_name=normalized_bank,
                month=normalized_month,
            )

        existing_external_ids = self._load_existing_transaction_ids_for_entries(entries)
        imported_transactions: list[Transaction] = []
        skipped_duplicates = 0
        seen_external_ids: set[str] = set()

        for entry in entries:
            if entry.external_id in seen_external_ids:
                skipped_duplicates += 1
                continue
            if entry.external_id in existing_external_ids:
                skipped_duplicates += 1
                continue

            seen_external_ids.add(entry.external_id)
            transaction = Transaction(
                user_id=self.user_id,
                title=_build_transaction_title(entry.description),
                description=entry.description,
                amount=abs(entry.amount),
                status=TransactionStatus.PAID,
                type=_resolve_transaction_type_enum(entry.transaction_type),
                due_date=entry.date,
                paid_at=datetime.combine(entry.date, datetime.min.time()),
                source="bank_import",
                external_id=entry.external_id,
                bank_name=entry.bank_name,
            )
            db.session.add(transaction)
            imported_transactions.append(transaction)

        db.session.commit()
        return BankImportConfirmation(
            bank_name=normalized_bank,
            month=normalized_month,
            imported_count=len(imported_transactions),
            skipped_duplicates=skipped_duplicates,
            replaced_count=replaced_count,
            transactions=imported_transactions,
        )

    def _load_existing_external_ids(
        self,
        parsed_entries: Iterable[ParsedEntry],
    ) -> set[str]:
        external_ids = sorted({entry.external_id for entry in parsed_entries})
        if not external_ids:
            return set()

        rows = (
            db.session.query(Transaction.external_id)
            .filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(Transaction.external_id.in_(external_ids))
            .all()
        )
        return {
            external_id
            for (external_id,) in rows
            if external_id is not None and external_id.strip()
        }

    def _load_existing_transaction_ids_for_entries(
        self,
        entries: Sequence[BankImportSelectedEntry],
    ) -> set[str]:
        external_ids = sorted({entry.external_id for entry in entries})
        if not external_ids:
            return set()

        rows = (
            db.session.query(Transaction.external_id)
            .filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(Transaction.external_id.in_(external_ids))
            .all()
        )
        return {
            external_id
            for (external_id,) in rows
            if external_id is not None and external_id.strip()
        }

    def _replace_month_transactions(self, *, bank_name: str, month: str) -> int:
        year, month_number = map(int, month.split("-"))
        rows = (
            Transaction.query.filter(Transaction.user_id == self.user_id)
            .filter(Transaction.deleted.is_(False))
            .filter(Transaction.source == "bank_import")
            .filter(Transaction.bank_name == bank_name)
            .filter(db.extract("year", Transaction.due_date) == year)
            .filter(db.extract("month", Transaction.due_date) == month_number)
            .all()
        )

        for transaction in rows:
            db.session.delete(transaction)
        db.session.flush()
        return len(rows)


def _normalize_bank_name(bank_name: str) -> str:
    normalized = " ".join(bank_name.strip().lower().split())
    if not normalized:
        raise ValueError("Bank name is required")

    canonical = _BANK_ALIASES.get(normalized)
    if canonical is None:
        raise ValueError(f"Unsupported bank: {bank_name!r}")
    return canonical


def _parse_entries(*, content: str, bank_name: str) -> list[ParsedEntry]:
    if bank_name == "nubank":
        return parse_nubank_csv(content)
    return parse_ofx(content, bank_name)


def _normalize_month(month: str) -> str:
    try:
        parsed = datetime.strptime(month, "%Y-%m")
    except ValueError as exc:
        raise ValueError("Month must use YYYY-MM format") from exc
    return parsed.strftime("%Y-%m")


def _normalize_mode(mode: str) -> str:
    normalized = mode.strip().lower()
    if normalized not in {"replace_month", "selective"}:
        raise ValueError("Mode must be replace_month or selective")
    return normalized


def _normalize_selected_entry(
    payload: dict[str, Any],
    *,
    expected_bank: str,
) -> BankImportSelectedEntry:
    external_id = _require_text(payload.get("external_id"), field_name="external_id")
    description = _require_text(payload.get("description"), field_name="description")
    bank_name = _normalize_bank_name(
        _require_text(payload.get("bank_name"), field_name="bank_name")
    )
    if bank_name != expected_bank:
        raise ValueError("Selected transaction bank does not match request bank")

    transaction_type = _require_text(
        payload.get("transaction_type"),
        field_name="transaction_type",
    ).lower()
    if transaction_type not in {"income", "expense"}:
        raise ValueError("transaction_type must be income or expense")

    raw_amount = payload.get("amount")
    try:
        amount = Decimal(str(raw_amount))
    except Exception as exc:  # pragma: no cover - Decimal uses broad exceptions
        raise ValueError("Invalid amount") from exc

    raw_date = _require_text(payload.get("date"), field_name="date")
    try:
        parsed_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError("date must use YYYY-MM-DD format") from exc

    return BankImportSelectedEntry(
        external_id=external_id,
        date=parsed_date,
        description=description,
        amount=amount,
        transaction_type=transaction_type,
        bank_name=bank_name,
    )


def _validate_entries_month(
    entries: Sequence[BankImportSelectedEntry],
    *,
    month: str,
) -> None:
    for entry in entries:
        if entry.date.strftime("%Y-%m") != month:
            raise ValueError(
                "All selected transactions must belong to the requested month"
            )


def _require_text(value: Any, *, field_name: str) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        raise ValueError(f"Missing required field: {field_name}")
    return text


def _build_transaction_title(description: str) -> str:
    normalized = " ".join(description.split())
    return normalized[:120]


def _resolve_transaction_type_enum(value: str) -> TransactionType:
    return TransactionType.INCOME if value == "income" else TransactionType.EXPENSE


__all__ = [
    "BankImportConfirmation",
    "BankImportPreview",
    "BankImportPreviewEntry",
    "BankImportSelectedEntry",
    "BankImportService",
]
