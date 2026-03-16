"""add J-tasks foundation models

Revision ID: j618_foundation
Revises: 20240614
Create Date: 2026-03-16 00:00:00.000000

Covers (GH #618 / canonical schema GH #401):
  - simulations
  - subscriptions
  - shared_entries + invitations
  - alerts + alert_preferences
  - fiscal_imports + fiscal_documents + receivable_entries + fiscal_adjustments
  - users.entitlements_version (new column on existing table)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "j618_foundation"
down_revision = "20240614"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # simulations
    # ------------------------------------------------------------------
    op.create_table(
        "simulations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("tool_id", sa.String(60), nullable=False),
        sa.Column("rule_version", sa.String(20), nullable=False),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("result", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "saved", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("goal_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["goal_id"], ["goals.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_simulations_tool_id", "simulations", ["tool_id"])
    op.create_index(
        "ix_simulations_user_created", "simulations", ["user_id", "created_at"]
    )
    op.create_index("ix_simulations_user_saved", "simulations", ["user_id", "saved"])

    # ------------------------------------------------------------------
    # subscriptions
    # ------------------------------------------------------------------
    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_code", sa.String(40), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "free",
                "trialing",
                "active",
                "past_due",
                "canceled",
                "expired",
                name="subscriptionstatus",
            ),
            nullable=False,
            server_default="free",
        ),
        sa.Column(
            "billing_cycle",
            sa.Enum("monthly", "semiannual", "annual", name="billingcycle"),
            nullable=True,
        ),
        sa.Column("provider", sa.String(40), nullable=True),
        sa.Column("provider_subscription_id", sa.String(120), nullable=True),
        sa.Column("provider_customer_id", sa.String(120), nullable=True),
        sa.Column("provider_event_id", sa.String(120), nullable=True),
        sa.Column("trial_ends_at", sa.DateTime(), nullable=True),
        sa.Column("current_period_start", sa.DateTime(), nullable=True),
        sa.Column("current_period_end", sa.DateTime(), nullable=True),
        sa.Column("grace_period_ends_at", sa.DateTime(), nullable=True),
        sa.Column("canceled_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_subscriptions_user_id"),
    )
    op.create_index(
        "ix_subscriptions_user_id", "subscriptions", ["user_id"], unique=True
    )
    op.create_index(
        "ix_subscriptions_provider_subscription_id",
        "subscriptions",
        ["provider_subscription_id"],
    )
    op.create_index(
        "ix_subscriptions_provider_event_id",
        "subscriptions",
        ["provider_event_id"],
    )

    # ------------------------------------------------------------------
    # shared_entries
    # ------------------------------------------------------------------
    op.create_table(
        "shared_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("owner_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "active", "revoked", name="sharedentriesstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "split_type",
            sa.Enum("equal", "percentage", "fixed", name="splittype"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["transaction_id"], ["transactions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shared_entries_owner_id", "shared_entries", ["owner_id"])
    op.create_index(
        "ix_shared_entries_transaction_id", "shared_entries", ["transaction_id"]
    )

    # ------------------------------------------------------------------
    # invitations
    # ------------------------------------------------------------------
    op.create_table(
        "invitations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shared_entry_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("from_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("to_user_email", sa.String(254), nullable=False),
        sa.Column("to_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("split_value", sa.Numeric(5, 2), nullable=True),
        sa.Column("share_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("message", sa.String(300), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "accepted",
                "rejected",
                "revoked",
                "expired",
                name="invitationstatus",
            ),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("responded_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["from_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["shared_entry_id"], ["shared_entries.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["to_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "shared_entry_id",
            "to_user_email",
            name="uq_invitations_shared_entry_email",
        ),
    )
    op.create_index(
        "ix_invitations_shared_entry_id", "invitations", ["shared_entry_id"]
    )
    op.create_index("ix_invitations_from_user_id", "invitations", ["from_user_id"])
    op.create_index(
        "ix_invitations_email_status", "invitations", ["to_user_email", "status"]
    )

    # ------------------------------------------------------------------
    # alerts
    # ------------------------------------------------------------------
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "sent", "failed", "skipped", name="alertstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("entity_type", sa.String(40), nullable=True),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alerts_user_category_triggered",
        "alerts",
        ["user_id", "category", "triggered_at"],
    )
    op.create_index("ix_alerts_user_sent_at", "alerts", ["user_id", "sent_at"])

    # ------------------------------------------------------------------
    # alert_preferences
    # ------------------------------------------------------------------
    op.create_table(
        "alert_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("category", sa.String(40), nullable=False),
        sa.Column(
            "enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "global_opt_out",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "category", name="uq_alert_preferences_user_category"
        ),
    )

    # ------------------------------------------------------------------
    # fiscal_imports
    # ------------------------------------------------------------------
    op.create_table(
        "fiscal_imports",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "processing",
                "preview_ready",
                "confirmed",
                "failed",
                name="fiscalimportstatus",
            ),
            nullable=False,
            server_default="processing",
        ),
        sa.Column("filename", sa.String(255), nullable=True),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("valid_rows", sa.Integer(), nullable=True),
        sa.Column("error_rows", sa.Integer(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fiscal_imports_user_id", "fiscal_imports", ["user_id"])

    # ------------------------------------------------------------------
    # fiscal_documents
    # ------------------------------------------------------------------
    op.create_table(
        "fiscal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("import_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("external_id", sa.String(120), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "service_invoice",
                "product_invoice",
                "receipt",
                "debit_note",
                "credit_note",
                name="fiscaldocumenttype",
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum(
                "issued",
                "canceled",
                "corrected",
                "settled",
                "partially_settled",
                name="fiscaldocumentstatus",
            ),
            nullable=False,
            server_default="issued",
        ),
        sa.Column("issued_at", sa.Date(), nullable=False),
        sa.Column("counterparty", sa.String(200), nullable=False),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="BRL"),
        sa.Column("competence_month", sa.Date(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["import_id"], ["fiscal_imports.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "external_id",
            name="uq_fiscal_documents_user_external_id",
        ),
    )
    op.create_index(
        "ix_fiscal_documents_user_issued",
        "fiscal_documents",
        ["user_id", "issued_at"],
    )

    # ------------------------------------------------------------------
    # receivable_entries
    # ------------------------------------------------------------------
    op.create_table(
        "receivable_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("expected_net_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("received_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("outstanding_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column(
            "reconciliation_status",
            sa.Enum("pending", "partial", "reconciled", name="reconciliationstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column(
            "linked_transaction_id", postgresql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("received_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["fiscal_document_id"], ["fiscal_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["linked_transaction_id"], ["transactions.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_receivable_entries_fiscal_document_id",
        "receivable_entries",
        ["fiscal_document_id"],
    )

    # ------------------------------------------------------------------
    # fiscal_adjustments
    # ------------------------------------------------------------------
    op.create_table(
        "fiscal_adjustments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fiscal_document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "type",
            sa.Enum(
                "tax",
                "fee",
                "withholding",
                "discount",
                "refund",
                name="fiscaladjustmenttype",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("applies_to", sa.String(20), nullable=False, server_default="gross"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(
            ["fiscal_document_id"], ["fiscal_documents.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_fiscal_adjustments_fiscal_document_id",
        "fiscal_adjustments",
        ["fiscal_document_id"],
    )

    # ------------------------------------------------------------------
    # users.entitlements_version (new column)
    # ------------------------------------------------------------------
    op.add_column(
        "users",
        sa.Column(
            "entitlements_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "entitlements_version")

    op.drop_index("ix_fiscal_adjustments_fiscal_document_id", "fiscal_adjustments")
    op.drop_table("fiscal_adjustments")

    op.drop_index("ix_receivable_entries_fiscal_document_id", "receivable_entries")
    op.drop_table("receivable_entries")

    op.drop_index("ix_fiscal_documents_user_issued", "fiscal_documents")
    op.drop_table("fiscal_documents")

    op.drop_index("ix_fiscal_imports_user_id", "fiscal_imports")
    op.drop_table("fiscal_imports")

    op.drop_table("alert_preferences")

    op.drop_index("ix_alerts_user_sent_at", "alerts")
    op.drop_index("ix_alerts_user_category_triggered", "alerts")
    op.drop_table("alerts")

    op.drop_index("ix_invitations_email_status", "invitations")
    op.drop_index("ix_invitations_from_user_id", "invitations")
    op.drop_index("ix_invitations_shared_entry_id", "invitations")
    op.drop_table("invitations")

    op.drop_index("ix_shared_entries_transaction_id", "shared_entries")
    op.drop_index("ix_shared_entries_owner_id", "shared_entries")
    op.drop_table("shared_entries")

    op.drop_index("ix_subscriptions_provider_event_id", "subscriptions")
    op.drop_index("ix_subscriptions_provider_subscription_id", "subscriptions")
    op.drop_index("ix_subscriptions_user_id", "subscriptions")
    op.drop_table("subscriptions")

    op.drop_index("ix_simulations_user_saved", "simulations")
    op.drop_index("ix_simulations_user_created", "simulations")
    op.drop_index("ix_simulations_tool_id", "simulations")
    op.drop_table("simulations")

    # Drop enum types created during upgrade
    for enum_name in (
        "subscriptionstatus",
        "billingcycle",
        "sharedentriesstatus",
        "splittype",
        "invitationstatus",
        "alertstatus",
        "fiscalimportstatus",
        "fiscaldocumenttype",
        "fiscaldocumentstatus",
        "reconciliationstatus",
        "fiscaladjustmenttype",
    ):
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
