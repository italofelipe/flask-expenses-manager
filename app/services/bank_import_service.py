from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable
from uuid import UUID

from app.extensions.database import db
from app.models.transaction import Transaction
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


__all__ = [
    "BankImportPreview",
    "BankImportPreviewEntry",
    "BankImportService",
]
