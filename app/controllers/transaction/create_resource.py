# mypy: disable-error-code=no-any-return

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from flask import Response
from flask_apispec import doc, use_kwargs
from flask_jwt_extended import get_jwt_identity, jwt_required

from app.extensions.database import db
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.schemas.transaction_schema import TransactionSchema

from .openapi import TRANSACTION_CREATE_DOC
from .utils import (
    _build_installment_amounts,
    _compat_error,
    _compat_success,
    _enforce_transaction_reference_ownership_or_error,
    _guard_revoked_token,
    _internal_error_response,
    _validate_recurring_payload,
    serialize_transaction,
)


def _compat_installment_amounts(total: Decimal, count: int) -> list[Decimal]:
    """
    Preserve legacy monkeypatch path on transaction.resources facade.

    Some regression tests and local debugging flows patch
    `app.controllers.transaction.resources._build_installment_amounts`.
    This resolver keeps that behavior while code is split by concern.
    """
    from . import resources as legacy_resources

    builder = getattr(
        legacy_resources,
        "_build_installment_amounts",
        _build_installment_amounts,
    )
    return builder(total, count)


class TransactionCreateMixin:
    """POST behavior for transaction creation (single and installments)."""

    @doc(**TRANSACTION_CREATE_DOC)  # type: ignore[misc]
    @jwt_required()  # type: ignore[misc]
    @use_kwargs(TransactionSchema, location="json")  # type: ignore[misc]
    def post(self, **kwargs: Any) -> Response:  # noqa: C901
        token_error = _guard_revoked_token()
        if token_error is not None:
            return token_error

        user_id = get_jwt_identity()
        user_uuid = UUID(user_id)

        if "type" in kwargs:
            kwargs["type"] = kwargs["type"].lower()

        recurring_error = _validate_recurring_payload(
            is_recurring=bool(kwargs.get("is_recurring", False)),
            due_date=kwargs.get("due_date"),
            start_date=kwargs.get("start_date"),
            end_date=kwargs.get("end_date"),
        )
        if recurring_error:
            return _compat_error(
                legacy_payload={"error": recurring_error},
                status_code=400,
                message=recurring_error,
                error_code="VALIDATION_ERROR",
            )

        reference_error = _enforce_transaction_reference_ownership_or_error(
            user_id=user_uuid,
            tag_id=kwargs.get("tag_id"),
            account_id=kwargs.get("account_id"),
            credit_card_id=kwargs.get("credit_card_id"),
        )
        if reference_error:
            return _compat_error(
                legacy_payload={"error": reference_error},
                status_code=400,
                message=reference_error,
                error_code="VALIDATION_ERROR",
            )

        if kwargs.get("is_installment") and kwargs.get("installment_count"):
            from uuid import uuid4

            from dateutil.relativedelta import relativedelta

            try:
                group_id = uuid4()
                total = Decimal(kwargs["amount"])
                count = int(kwargs["installment_count"])
                base_date = kwargs["due_date"]
                installment_amounts = _compat_installment_amounts(total, count)
                title = kwargs["title"]
                if "type" in kwargs:
                    kwargs["type"] = kwargs["type"].lower()

                transactions = []
                for i in range(count):
                    due = base_date + relativedelta(months=i)
                    transaction = Transaction(
                        user_id=user_uuid,
                        title=f"{title} ({i + 1}/{count})",
                        amount=installment_amounts[i],
                        type=TransactionType(kwargs["type"]),
                        due_date=due,
                        start_date=kwargs.get("start_date"),
                        end_date=kwargs.get("end_date"),
                        description=kwargs.get("description"),
                        observation=kwargs.get("observation"),
                        is_recurring=kwargs.get("is_recurring", False),
                        is_installment=True,
                        installment_count=count,
                        tag_id=kwargs.get("tag_id"),
                        account_id=kwargs.get("account_id"),
                        credit_card_id=kwargs.get("credit_card_id"),
                        status=TransactionStatus(
                            kwargs.get("status", "pending").lower()
                        ),
                        currency=kwargs.get("currency", "BRL"),
                        installment_group_id=group_id,
                    )
                    transactions.append(transaction)

                db.session.add_all(transactions)
                db.session.commit()

                created_data = [serialize_transaction(item) for item in transactions]
                return _compat_success(
                    legacy_payload={
                        "message": "Transações parceladas criadas com sucesso",
                        "transactions": created_data,
                    },
                    status_code=201,
                    message="Transações parceladas criadas com sucesso",
                    data={"transactions": created_data},
                )
            except Exception:
                db.session.rollback()
                return _internal_error_response(
                    message="Erro ao criar transações parceladas",
                    log_context="transaction.installment.create_failed",
                )

        try:
            transaction = Transaction(
                user_id=user_uuid,
                title=kwargs["title"],
                amount=kwargs["amount"],
                type=TransactionType(kwargs["type"]),
                due_date=kwargs["due_date"],
                start_date=kwargs.get("start_date"),
                end_date=kwargs.get("end_date"),
                description=kwargs.get("description"),
                observation=kwargs.get("observation"),
                is_recurring=kwargs.get("is_recurring", False),
                is_installment=kwargs.get("is_installment", False),
                installment_count=kwargs.get("installment_count"),
                tag_id=kwargs.get("tag_id"),
                account_id=kwargs.get("account_id"),
                credit_card_id=kwargs.get("credit_card_id"),
                status=TransactionStatus(kwargs.get("status", "pending").lower()),
                currency=kwargs.get("currency", "BRL"),
            )

            db.session.add(transaction)
            db.session.commit()

            created_data = [serialize_transaction(transaction)]
            return _compat_success(
                legacy_payload={
                    "message": "Transação criada com sucesso",
                    "transaction": created_data,
                },
                status_code=201,
                message="Transação criada com sucesso",
                data={"transaction": created_data},
            )
        except Exception:
            db.session.rollback()
            return _internal_error_response(
                message="Erro ao criar transação",
                log_context="transaction.create_failed",
            )
