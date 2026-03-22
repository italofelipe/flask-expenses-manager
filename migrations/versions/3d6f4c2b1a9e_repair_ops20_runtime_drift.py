"""Repair OPS-20 runtime drift for billing, sharing and fiscal domains.

Revision ID: 3d6f4c2b1a9e
Revises: 7f9c2d1a4b6e
Create Date: 2026-03-22 23:15:00.000000
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "3d6f4c2b1a9e"
down_revision = "7f9c2d1a4b6e"
branch_labels = None
depends_on = None


def _rename_postgres_enum_value(type_name: str, old_value: str, new_value: str) -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_enum e ON e.enumtypid = t.oid
                    WHERE t.typname = :type_name
                      AND e.enumlabel = :old_value
                ) AND NOT EXISTS (
                    SELECT 1
                    FROM pg_type t
                    JOIN pg_enum e ON e.enumtypid = t.oid
                    WHERE t.typname = :type_name
                      AND e.enumlabel = :new_value
                ) THEN
                    EXECUTE format(
                        'ALTER TYPE %I RENAME VALUE %L TO %L',
                        :type_name,
                        :old_value,
                        :new_value
                    );
                END IF;
            END
            $$;
            """
        ).bindparams(
            type_name=type_name,
            old_value=old_value,
            new_value=new_value,
        )
    )


def _repair_invitation_columns() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("invitations")}

    if "token" not in columns:
        op.add_column(
            "invitations",
            sa.Column("token", sa.String(length=64), nullable=True),
        )
    if "expires_at" not in columns:
        op.add_column(
            "invitations",
            sa.Column("expires_at", sa.DateTime(), nullable=True),
        )

    if bind.dialect.name == "postgresql":
        op.execute(
            """
            UPDATE invitations
            SET
                token = COALESCE(
                    token,
                    md5(id::text || clock_timestamp()::text || random()::text)
                    || md5(random()::text || id::text)
                ),
                expires_at = COALESCE(expires_at, created_at + interval '48 hours')
            WHERE status = 'pending'
            """
        )

    indexes = {index["name"] for index in inspector.get_indexes("invitations")}
    if "ix_invitations_token" not in indexes:
        op.create_index("ix_invitations_token", "invitations", ["token"], unique=True)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        enum_renames = {
            "subscriptionstatus": {
                "FREE": "free",
                "TRIALING": "trialing",
                "ACTIVE": "active",
                "PAST_DUE": "past_due",
                "CANCELED": "canceled",
                "EXPIRED": "expired",
            },
            "billingcycle": {
                "MONTHLY": "monthly",
                "SEMIANNUAL": "semiannual",
                "ANNUAL": "annual",
            },
            "sharedentriesstatus": {
                "PENDING": "pending",
                "ACTIVE": "active",
                "REVOKED": "revoked",
            },
            "splittype": {
                "EQUAL": "equal",
                "PERCENTAGE": "percentage",
                "FIXED": "fixed",
            },
            "invitationstatus": {
                "PENDING": "pending",
                "ACCEPTED": "accepted",
                "REJECTED": "rejected",
                "REVOKED": "revoked",
                "EXPIRED": "expired",
            },
            "fiscalimportstatus": {
                "PROCESSING": "processing",
                "PREVIEW_READY": "preview_ready",
                "CONFIRMED": "confirmed",
                "FAILED": "failed",
            },
            "fiscaldocumenttype": {
                "SERVICE_INVOICE": "service_invoice",
                "PRODUCT_INVOICE": "product_invoice",
                "RECEIPT": "receipt",
                "DEBIT_NOTE": "debit_note",
                "CREDIT_NOTE": "credit_note",
            },
            "fiscaldocumentstatus": {
                "ISSUED": "issued",
                "CANCELED": "canceled",
                "CORRECTED": "corrected",
                "SETTLED": "settled",
                "PARTIALLY_SETTLED": "partially_settled",
            },
            "reconciliationstatus": {
                "PENDING": "pending",
                "PARTIAL": "partial",
                "RECONCILED": "reconciled",
            },
            "fiscaladjustmenttype": {
                "TAX": "tax",
                "FEE": "fee",
                "WITHHOLDING": "withholding",
                "DISCOUNT": "discount",
                "REFUND": "refund",
            },
        }

        for type_name, rename_map in enum_renames.items():
            for old_value, new_value in rename_map.items():
                _rename_postgres_enum_value(type_name, old_value, new_value)

    _repair_invitation_columns()


def downgrade() -> None:
    # Repair migration only: keep runtime/schema compatible on rollback as well.
    pass
