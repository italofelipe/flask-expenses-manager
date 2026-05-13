"""GraphQL queries for the Fiscal domain (#1247).

Read-only surface (canonical per ADR-0002).
Wraps the service layer — no direct ORM access.
"""

from __future__ import annotations

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import (
    FiscalDocumentListType,
    FiscalDocumentType,
    ReceivableEntryType,
    ReceivableListType,
    ReceivableSummaryType,
)
from app.models.fiscal import FiscalDocument, ReceivableEntry
from app.services.fiscal_service import list_fiscal_documents
from app.services.receivable_service import get_revenue_summary, list_receivables

_DISCLAIMER = (
    "Este valor é estimativo e não substitui cálculo fiscal por profissional habilitado"
)


def _to_fiscal_doc_type(doc: FiscalDocument) -> FiscalDocumentType:
    return FiscalDocumentType(
        id=str(doc.id),
        external_id=doc.external_id,
        type=doc.type.value,
        status=doc.status.value,
        issued_at=doc.issued_at.isoformat() if doc.issued_at else "",
        counterparty=doc.counterparty,
        gross_amount=doc.gross_amount,
        currency=doc.currency,
        description=doc.description,
        created_at=doc.created_at.isoformat() if doc.created_at else "",
    )


def _to_receivable_type(entry: ReceivableEntry) -> ReceivableEntryType:
    return ReceivableEntryType(
        id=str(entry.id),
        fiscal_document_id=str(entry.fiscal_document_id),
        expected_net_amount=entry.expected_net_amount,
        received_amount=entry.received_amount,
        outstanding_amount=entry.outstanding_amount,
        reconciliation_status=entry.reconciliation_status.value,
        received_at=entry.received_at.isoformat() if entry.received_at else None,
        created_at=entry.created_at.isoformat() if entry.created_at else "",
        disclaimer=_DISCLAIMER,
    )


class FiscalQueryMixin:
    receivables = graphene.Field(
        ReceivableListType,
        status=graphene.String(description="Filter: pending | received | cancelled"),
    )
    receivables_summary = graphene.Field(ReceivableSummaryType)
    fiscal_documents = graphene.Field(
        FiscalDocumentListType,
        type=graphene.String(
            description=(
                "Filter by document type: service_invoice | product_invoice | "
                "receipt | debit_note | credit_note"
            )
        ),
    )

    @log_graphql_resolver("receivables")
    def resolve_receivables(
        self,
        _info: graphene.ResolveInfo,
        status: str | None = None,
    ) -> ReceivableListType:
        user = get_current_user_required()
        entries = list_receivables(str(user.id), status=status)
        return ReceivableListType(
            receivables=[_to_receivable_type(e) for e in entries],
            total=len(entries),
        )

    @log_graphql_resolver("receivablesSummary")
    def resolve_receivables_summary(
        self, _info: graphene.ResolveInfo
    ) -> ReceivableSummaryType:
        user = get_current_user_required()
        summary = get_revenue_summary(str(user.id))
        return ReceivableSummaryType(
            expected_total=summary["expected_total"],
            received_total=summary["received_total"],
            pending_total=summary["pending_total"],
            disclaimer=summary["disclaimer"],
        )

    @log_graphql_resolver("fiscalDocuments")
    def resolve_fiscal_documents(
        self,
        _info: graphene.ResolveInfo,
        type: str | None = None,
    ) -> FiscalDocumentListType:
        user = get_current_user_required()
        docs = list_fiscal_documents(str(user.id), doc_type=type)
        return FiscalDocumentListType(
            fiscal_documents=[_to_fiscal_doc_type(d) for d in docs],
            total=len(docs),
        )
