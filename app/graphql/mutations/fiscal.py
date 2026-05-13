"""GraphQL mutations for the Fiscal domain (#1247).

Per ADR-0002, REST is the canonical write surface. These mutations are
deprecated shims — kept for GraphQL-only clients. New integrations should
use the REST endpoints listed in each deprecation_reason.
"""

from __future__ import annotations

from datetime import date as _date
from decimal import Decimal, InvalidOperation

import graphene

from app.graphql.auth import get_current_user_required
from app.graphql.errors import build_public_graphql_error
from app.graphql.observability import log_graphql_resolver
from app.graphql.types import (
    FiscalDocumentPayload,
    FiscalDocumentType,
    ReceivableEntryType,
    ReceivablePayload,
)
from app.services.fiscal_service import (
    FiscalDocumentNotFoundError,
    create_fiscal_document,
)
from app.services.receivable_service import (
    ReceivableAlreadySettledError,
    ReceivableNotFoundError,
    cancel_receivable,
    create_receivable,
    mark_received,
)

_DISCLAIMER = (
    "Este valor é estimativo e não substitui cálculo fiscal por profissional habilitado"
)


def _parse_date(value: str) -> _date:
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            from datetime import datetime

            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {value!r}. Use YYYY-MM-DD.")


def _to_receivable_type(entry: object) -> ReceivableEntryType:
    return ReceivableEntryType(
        id=str(entry.id),  # type: ignore[attr-defined]
        fiscal_document_id=str(entry.fiscal_document_id),  # type: ignore[attr-defined]
        expected_net_amount=entry.expected_net_amount,  # type: ignore[attr-defined]
        received_amount=entry.received_amount,  # type: ignore[attr-defined]
        outstanding_amount=entry.outstanding_amount,  # type: ignore[attr-defined]
        reconciliation_status=entry.reconciliation_status.value,  # type: ignore[attr-defined]
        received_at=(
            entry.received_at.isoformat()  # type: ignore[attr-defined]
            if entry.received_at  # type: ignore[attr-defined]
            else None
        ),
        created_at=(
            entry.created_at.isoformat()  # type: ignore[attr-defined]
            if entry.created_at  # type: ignore[attr-defined]
            else ""
        ),
        disclaimer=_DISCLAIMER,
    )


def _to_fiscal_doc_type(doc: object) -> FiscalDocumentType:
    return FiscalDocumentType(
        id=str(doc.id),  # type: ignore[attr-defined]
        external_id=doc.external_id,  # type: ignore[attr-defined]
        type=doc.type.value,  # type: ignore[attr-defined]
        status=doc.status.value,  # type: ignore[attr-defined]
        issued_at=(
            doc.issued_at.isoformat() if doc.issued_at else ""  # type: ignore[attr-defined]
        ),
        counterparty=doc.counterparty,  # type: ignore[attr-defined]
        gross_amount=doc.gross_amount,  # type: ignore[attr-defined]
        currency=doc.currency,  # type: ignore[attr-defined]
        description=doc.description,  # type: ignore[attr-defined]
        created_at=(
            doc.created_at.isoformat() if doc.created_at else ""  # type: ignore[attr-defined]
        ),
    )


class CreateReceivableMutation(graphene.Mutation):
    class Arguments:
        description = graphene.String(required=True)
        amount = graphene.String(required=True)
        expected_date = graphene.String(required=True, description="YYYY-MM-DD")
        category = graphene.String()

    Output = ReceivablePayload

    @log_graphql_resolver("createReceivable")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        description: str,
        amount: str,
        expected_date: str,
        category: str | None = None,
    ) -> ReceivablePayload:
        user = get_current_user_required()
        description = description.strip()
        if not description:
            raise build_public_graphql_error(
                "description is required", code="VALIDATION_ERROR"
            )
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation as exc:
            raise build_public_graphql_error(
                "amount must be a valid decimal", code="VALIDATION_ERROR"
            ) from exc
        try:
            parsed_date = _parse_date(expected_date)
        except ValueError as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        _doc, entry = create_receivable(
            user_id=str(user.id),
            description=description,
            amount=decimal_amount,
            expected_date=parsed_date,
            category=category,
        )
        return ReceivablePayload(
            ok=True,
            message="Recebível criado com sucesso.",
            errors=[],
            data=_to_receivable_type(entry),
        )


class MarkReceivableReceivedMutation(graphene.Mutation):
    class Arguments:
        entry_id = graphene.UUID(required=True)
        received_date = graphene.String(required=True, description="YYYY-MM-DD")
        received_amount = graphene.String()

    Output = ReceivablePayload

    @log_graphql_resolver("markReceivableReceived")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        entry_id: object,
        received_date: str,
        received_amount: str | None = None,
    ) -> ReceivablePayload:
        user = get_current_user_required()
        try:
            parsed_date = _parse_date(received_date)
        except ValueError as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        decimal_received: Decimal | None = None
        if received_amount is not None:
            try:
                decimal_received = Decimal(str(received_amount))
            except InvalidOperation as exc:
                raise build_public_graphql_error(
                    "received_amount must be a valid decimal", code="VALIDATION_ERROR"
                ) from exc

        try:
            entry = mark_received(
                str(entry_id), str(user.id), parsed_date, decimal_received
            )
        except ReceivableNotFoundError as exc:
            raise build_public_graphql_error(str(exc), code="NOT_FOUND") from exc
        except ReceivableAlreadySettledError as exc:
            raise build_public_graphql_error(str(exc), code="ALREADY_SETTLED") from exc

        return ReceivablePayload(
            ok=True,
            message="Recebível marcado como recebido.",
            errors=[],
            data=_to_receivable_type(entry),
        )


class CancelReceivableMutation(graphene.Mutation):
    class Arguments:
        entry_id = graphene.UUID(required=True)

    Output = ReceivablePayload

    @log_graphql_resolver("cancelReceivable")
    def mutate(
        self, _info: graphene.ResolveInfo, entry_id: object
    ) -> ReceivablePayload:
        user = get_current_user_required()
        try:
            entry = cancel_receivable(str(entry_id), str(user.id))
        except ReceivableNotFoundError as exc:
            raise build_public_graphql_error(str(exc), code="NOT_FOUND") from exc
        except ReceivableAlreadySettledError as exc:
            raise build_public_graphql_error(str(exc), code="ALREADY_SETTLED") from exc

        return ReceivablePayload(
            ok=True,
            message="Recebível cancelado com sucesso.",
            errors=[],
            data=_to_receivable_type(entry),
        )


class CreateFiscalDocumentMutation(graphene.Mutation):
    class Arguments:
        type = graphene.String(
            required=True,
            description=(
                "service_invoice | product_invoice | receipt | debit_note | credit_note"
            ),
        )
        amount = graphene.String(required=True)
        issued_at = graphene.String(required=True, description="YYYY-MM-DD")
        counterpart_name = graphene.String()
        external_id = graphene.String()

    Output = FiscalDocumentPayload

    @log_graphql_resolver("createFiscalDocument")
    def mutate(
        self,
        _info: graphene.ResolveInfo,
        type: str,
        amount: str,
        issued_at: str,
        counterpart_name: str | None = None,
        external_id: str | None = None,
    ) -> FiscalDocumentPayload:
        user = get_current_user_required()
        try:
            decimal_amount = Decimal(str(amount))
        except InvalidOperation as exc:
            raise build_public_graphql_error(
                "amount must be a valid decimal", code="VALIDATION_ERROR"
            ) from exc
        try:
            parsed_date = _parse_date(issued_at)
        except ValueError as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        try:
            doc = create_fiscal_document(
                user_id=str(user.id),
                doc_type=type,
                amount=decimal_amount,
                issued_at=parsed_date,
                counterpart_name=counterpart_name,
                external_id=external_id,
            )
        except (ValueError, FiscalDocumentNotFoundError) as exc:
            raise build_public_graphql_error(str(exc), code="VALIDATION_ERROR") from exc

        return FiscalDocumentPayload(
            ok=True,
            message="Documento fiscal criado com sucesso.",
            errors=[],
            data=_to_fiscal_doc_type(doc),
        )
