"""GraphQL mutations for the Bank Statement Import domain (#1148)."""

from __future__ import annotations

from typing import Any

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import (
    BankImportConfirmationPayload,
    BankImportPreviewEntryType,
    BankImportPreviewPayload,
    BankImportPreviewType,
    ImportedTransactionType,
)
from app.services.bank_import_service import BankImportService


class SelectedEntryInput(graphene.InputObjectType):
    external_id = graphene.String(required=True)
    date = graphene.String(required=True)
    description = graphene.String(required=True)
    amount = graphene.String(required=True)
    transaction_type = graphene.String(required=True)
    bank_name = graphene.String(required=True)


def _preview_entry_to_type(entry: Any) -> BankImportPreviewEntryType:
    return BankImportPreviewEntryType(
        external_id=entry.external_id,
        date=entry.date,
        description=entry.description,
        amount=str(entry.amount),
        transaction_type=entry.transaction_type,
        bank_name=entry.bank_name,
        is_duplicate=entry.is_duplicate,
        duplicate_reason=entry.duplicate_reason,
    )


class PreviewBankStatementMutation(graphene.Mutation):
    """Parse a bank statement text and return a deduplication preview.

    The client submits the raw text content (CSV for Nubank, OFX for others)
    together with a bank identifier.  No data is written to the database.
    """

    class Arguments:
        content = graphene.String(
            required=True, description="Raw bank statement text (CSV or OFX)."
        )
        bank_name = graphene.String(
            required=True, description="Bank identifier (e.g. 'nubank', 'itau')."
        )

    Output = BankImportPreviewPayload

    @log_graphql_resolver("previewBankStatement")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        content: str,
        bank_name: str,
    ) -> BankImportPreviewPayload:
        user = get_current_user_required()
        try:
            service = BankImportService(user.id)
            preview = service.build_preview(content=content, bank_name=bank_name)
        except ValueError as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        return BankImportPreviewPayload(
            ok=True,
            message="Preview gerado com sucesso.",
            errors=[],
            data=BankImportPreviewType(
                bank_name=preview.bank_name,
                entries=[_preview_entry_to_type(e) for e in preview.entries],
                total_entries=preview.total_entries,
                duplicate_entries=preview.duplicate_entries,
                new_entries=preview.new_entries,
            ),
        )


class ConfirmBankImportMutation(graphene.Mutation):
    """Persist a subset of bank statement entries as transactions.

    ``mode`` controls how existing data is handled:

    - ``selective``: skip duplicates, import only new entries.
    - ``replace_month``: delete all existing bank-imported transactions for
      the given month/bank before importing the selected set.
    """

    class Arguments:
        bank_name = graphene.String(required=True)
        month = graphene.String(required=True, description="Month in YYYY-MM format.")
        mode = graphene.String(
            required=True, description="'selective' or 'replace_month'."
        )
        selected_entries = graphene.List(
            graphene.NonNull(SelectedEntryInput),
            required=True,
        )

    Output = BankImportConfirmationPayload

    @log_graphql_resolver("confirmBankImport")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        bank_name: str,
        month: str,
        mode: str,
        selected_entries: list[Any],
    ) -> BankImportConfirmationPayload:
        user = get_current_user_required()

        # Convert graphene InputObjectType instances to plain dicts that the
        # service expects.
        raw_entries = [
            {
                "external_id": e.external_id,
                "date": e.date,
                "description": e.description,
                "amount": e.amount,
                "transaction_type": e.transaction_type,
                "bank_name": e.bank_name,
            }
            for e in selected_entries
        ]

        try:
            service = BankImportService(user.id)
            result = service.confirm_import(
                bank_name=bank_name,
                month=month,
                mode=mode,
                selected_entries=raw_entries,
            )
        except ValueError as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        imported_transactions = [
            ImportedTransactionType(
                id=str(t.id),
                title=t.title,
                amount=str(t.amount),
                type=t.type.value if hasattr(t.type, "value") else str(t.type),
                due_date=t.due_date.isoformat() if t.due_date else "",
                bank_name=t.bank_name,
                external_id=t.external_id,
            )
            for t in result.transactions
        ]

        return BankImportConfirmationPayload(
            ok=True,
            message="Importação confirmada com sucesso.",
            errors=[],
            bank_name=result.bank_name,
            month=result.month,
            imported_count=result.imported_count,
            skipped_duplicates=result.skipped_duplicates,
            replaced_count=result.replaced_count,
            transactions=imported_transactions,
        )


__all__ = [
    "ConfirmBankImportMutation",
    "PreviewBankStatementMutation",
    "SelectedEntryInput",
]
