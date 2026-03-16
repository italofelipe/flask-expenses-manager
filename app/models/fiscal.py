# mypy: disable-error-code="name-defined"
"""Fiscal models — J14 (NF import, receivables, adjustments).

Models:
  FiscalImport       — CSV import batch operation
  FiscalDocument     — individual fiscal document (NF, receipt, …)
  ReceivableEntry    — expected/received amounts for a FiscalDocument
  FiscalAdjustment   — auditable manual adjustment on a FiscalDocument

IMPORTANT: ReceivableEntry.expected_net_amount is **advisory-only**.
Every endpoint that exposes this field MUST include the disclaimer:
  "Este valor é estimativo e não substitui cálculo fiscal por profissional habilitado"
"""

from __future__ import annotations

import enum
import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions.database import db
from app.utils.datetime_utils import utc_now_naive


class FiscalImportStatus(enum.Enum):
    PROCESSING = "processing"
    PREVIEW_READY = "preview_ready"
    CONFIRMED = "confirmed"
    FAILED = "failed"


class FiscalDocumentType(enum.Enum):
    SERVICE_INVOICE = "service_invoice"
    PRODUCT_INVOICE = "product_invoice"
    RECEIPT = "receipt"
    DEBIT_NOTE = "debit_note"
    CREDIT_NOTE = "credit_note"


class FiscalDocumentStatus(enum.Enum):
    ISSUED = "issued"
    CANCELED = "canceled"
    CORRECTED = "corrected"
    SETTLED = "settled"
    PARTIALLY_SETTLED = "partially_settled"


class ReconciliationStatus(enum.Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    RECONCILED = "reconciled"


class FiscalAdjustmentType(enum.Enum):
    TAX = "tax"
    FEE = "fee"
    WITHHOLDING = "withholding"
    DISCOUNT = "discount"
    REFUND = "refund"


class FiscalImport(db.Model):
    """Tracks a CSV import batch operation."""

    __tablename__ = "fiscal_imports"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False, index=True
    )
    status = db.Column(
        db.Enum(FiscalImportStatus),
        nullable=False,
        default=FiscalImportStatus.PROCESSING,
    )
    filename = db.Column(db.String(255), nullable=True)
    total_rows = db.Column(db.Integer, nullable=True)
    valid_rows = db.Column(db.Integer, nullable=True)
    error_rows = db.Column(db.Integer, nullable=True)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    documents = db.relationship(
        "FiscalDocument", back_populates="import_batch", lazy="dynamic"
    )

    def __repr__(self) -> str:
        return f"<FiscalImport id={self.id} status={self.status}>"


class FiscalDocument(db.Model):
    """An individual imported fiscal document."""

    __tablename__ = "fiscal_documents"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    import_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("fiscal_imports.id"), nullable=True
    )
    external_id = db.Column(db.String(120), nullable=False)
    type = db.Column(db.Enum(FiscalDocumentType), nullable=False)
    status = db.Column(
        db.Enum(FiscalDocumentStatus),
        nullable=False,
        default=FiscalDocumentStatus.ISSUED,
    )
    issued_at = db.Column(db.Date, nullable=False)
    counterparty = db.Column(db.String(200), nullable=False)
    gross_amount = db.Column(db.Numeric(14, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default="BRL")
    competence_month = db.Column(db.Date, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    description = db.Column(db.String(500), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    import_batch = db.relationship("FiscalImport", back_populates="documents")
    receivable_entries = db.relationship(
        "ReceivableEntry",
        back_populates="fiscal_document",
        cascade="all, delete-orphan",
    )
    adjustments = db.relationship(
        "FiscalAdjustment",
        back_populates="fiscal_document",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        db.Index("ix_fiscal_documents_user_issued", "user_id", "issued_at"),
        db.UniqueConstraint(
            "user_id", "external_id", name="uq_fiscal_documents_user_external_id"
        ),
    )

    def __repr__(self) -> str:
        return f"<FiscalDocument ext={self.external_id} type={self.type}>"


class ReceivableEntry(db.Model):
    """Expected and received amounts linked to a FiscalDocument.

    IMPORTANT: ``expected_net_amount`` is **advisory-only** and must NEVER be
    presented as an official fiscal calculation.
    """

    __tablename__ = "receivable_entries"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    fiscal_document_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("fiscal_documents.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    # advisory-only — see module docstring
    expected_net_amount = db.Column(db.Numeric(14, 2), nullable=True)
    received_amount = db.Column(db.Numeric(14, 2), nullable=True)
    # outstanding_amount = expected_net_amount - received_amount (calculated in app)
    outstanding_amount = db.Column(db.Numeric(14, 2), nullable=True)
    reconciliation_status = db.Column(
        db.Enum(ReconciliationStatus),
        nullable=False,
        default=ReconciliationStatus.PENDING,
    )
    linked_transaction_id = db.Column(
        UUID(as_uuid=True), db.ForeignKey("transactions.id"), nullable=True
    )
    received_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )

    fiscal_document = db.relationship(
        "FiscalDocument", back_populates="receivable_entries"
    )

    def __repr__(self) -> str:
        return (
            f"<ReceivableEntry doc={self.fiscal_document_id}"
            f" status={self.reconciliation_status}>"
        )


class FiscalAdjustment(db.Model):
    """Auditable manual adjustment applied to a FiscalDocument."""

    __tablename__ = "fiscal_adjustments"

    id = db.Column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, nullable=False
    )
    fiscal_document_id = db.Column(
        UUID(as_uuid=True),
        db.ForeignKey("fiscal_documents.id"),
        nullable=False,
        index=True,
    )
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey("users.id"), nullable=False)
    type = db.Column(db.Enum(FiscalAdjustmentType), nullable=False)
    description = db.Column(db.String(300), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    # "gross" | "net"
    applies_to = db.Column(db.String(20), nullable=False, default="gross")
    created_at = db.Column(db.DateTime, nullable=False, default=utc_now_naive)
    updated_at = db.Column(
        db.DateTime, nullable=False, default=utc_now_naive, onupdate=utc_now_naive
    )
    deleted_at = db.Column(db.DateTime, nullable=True)  # soft delete for audit trail

    fiscal_document = db.relationship("FiscalDocument", back_populates="adjustments")

    def __repr__(self) -> str:
        return (
            f"<FiscalAdjustment type={self.type} amount={self.amount}"
            f" doc={self.fiscal_document_id}>"
        )
