"""Unit tests for app/services/fiscal_service.py."""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from app.extensions.database import db
from app.models.user import User
from app.services.fiscal_service import (
    FiscalDocumentNotFoundError,
    _to_uuid,
    create_fiscal_document,
    get_fiscal_document,
    list_fiscal_documents,
)


def _create_user(app_ctx: Any) -> User:
    user = User(
        id=uuid.uuid4(),
        name="Fiscal User",
        email=f"fiscal-{uuid.uuid4().hex[:8]}@example.com",
        password="hashed-pw",
    )
    db.session.add(user)
    db.session.commit()
    return user


class TestToUuid:
    def test_passthrough_for_uuid_instance(self):
        uid = uuid.uuid4()
        assert _to_uuid(uid) is uid

    def test_parses_string_uuid(self):
        uid = uuid.uuid4()
        assert _to_uuid(str(uid)) == uid


class TestCreateFiscalDocument:
    def test_raises_for_invalid_doc_type(self, app):
        with app.app_context():
            user = _create_user(app)
            with pytest.raises(ValueError, match="Invalid doc_type"):
                create_fiscal_document(
                    user_id=str(user.id),
                    doc_type="invalid_type",
                    amount=Decimal("100.00"),
                    issued_at=date.today(),
                )

    def test_creates_document_without_raw_data(self, app):
        with app.app_context():
            user = _create_user(app)
            doc = create_fiscal_document(
                user_id=str(user.id),
                doc_type="service_invoice",
                amount=Decimal("500.00"),
                issued_at=date(2025, 1, 15),
            )
            assert doc.id is not None
            assert doc.description is None
            assert doc.gross_amount == Decimal("500.00")

    def test_creates_document_with_raw_data(self, app):
        with app.app_context():
            user = _create_user(app)
            doc = create_fiscal_document(
                user_id=str(user.id),
                doc_type="receipt",
                amount=Decimal("200.00"),
                issued_at=date(2025, 2, 1),
                raw_data={"tax_rate": "15%"},
            )
            assert doc.description is not None
            assert "tax_rate" in doc.description

    def test_generates_external_id_when_not_provided(self, app):
        with app.app_context():
            user = _create_user(app)
            doc = create_fiscal_document(
                user_id=str(user.id),
                doc_type="service_invoice",
                amount=Decimal("100.00"),
                issued_at=date.today(),
            )
            assert doc.external_id is not None
            assert len(doc.external_id) > 0

    def test_uses_provided_external_id(self, app):
        with app.app_context():
            user = _create_user(app)
            ext_id = "EXT-001"
            doc = create_fiscal_document(
                user_id=str(user.id),
                doc_type="service_invoice",
                amount=Decimal("100.00"),
                issued_at=date.today(),
                external_id=ext_id,
            )
            assert doc.external_id == ext_id


class TestListFiscalDocuments:
    def test_returns_empty_list_when_no_documents(self, app):
        with app.app_context():
            user = _create_user(app)
            docs = list_fiscal_documents(str(user.id))
            assert docs == []

    def test_returns_all_documents_when_no_type_filter(self, app):
        with app.app_context():
            user = _create_user(app)
            create_fiscal_document(
                str(user.id), "service_invoice", Decimal("100"), date.today()
            )
            create_fiscal_document(str(user.id), "receipt", Decimal("50"), date.today())
            docs = list_fiscal_documents(str(user.id))
            assert len(docs) == 2

    def test_filters_by_valid_doc_type(self, app):
        with app.app_context():
            user = _create_user(app)
            create_fiscal_document(
                str(user.id), "service_invoice", Decimal("100"), date.today()
            )
            create_fiscal_document(str(user.id), "receipt", Decimal("50"), date.today())
            invoices = list_fiscal_documents(str(user.id), doc_type="service_invoice")
            assert len(invoices) == 1
            assert invoices[0].type.value == "service_invoice"

    def test_returns_empty_list_for_invalid_doc_type(self, app):
        with app.app_context():
            user = _create_user(app)
            create_fiscal_document(
                str(user.id), "service_invoice", Decimal("100"), date.today()
            )
            docs = list_fiscal_documents(str(user.id), doc_type="nonexistent_type")
            assert docs == []


class TestGetFiscalDocument:
    def test_returns_document_for_correct_user(self, app):
        with app.app_context():
            user = _create_user(app)
            created = create_fiscal_document(
                str(user.id), "service_invoice", Decimal("100"), date.today()
            )
            fetched = get_fiscal_document(str(created.id), str(user.id))
            assert fetched.id == created.id

    def test_raises_not_found_for_nonexistent_document(self, app):
        with app.app_context():
            user = _create_user(app)
            with pytest.raises(FiscalDocumentNotFoundError):
                get_fiscal_document(str(uuid.uuid4()), str(user.id))

    def test_raises_not_found_for_wrong_user(self, app):
        with app.app_context():
            owner = _create_user(app)
            other = _create_user(app)
            doc = create_fiscal_document(
                str(owner.id), "service_invoice", Decimal("100"), date.today()
            )
            with pytest.raises(FiscalDocumentNotFoundError):
                get_fiscal_document(str(doc.id), str(other.id))
