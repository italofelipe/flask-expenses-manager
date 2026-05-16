"""Promote founder subscription to premium (#1250).

Revision ID: ai6
Revises: ai5
Create Date: 2026-05-16

"""

from __future__ import annotations

import uuid

import sqlalchemy as sa
from alembic import op

revision = "ai6"
down_revision = "ai5"
branch_labels = None
depends_on = None

_PREMIUM_FEATURES = (
    "basic_simulations",
    "wallet_read",
    "advanced_simulations",
    "export_pdf",
    "shared_entries",
    "focus_mode",
    "email_reminders",
)
_FOUNDER_USER_ID = "ee8d33ca0ac041cc95bdc4be49cbcbd5"
_FOUNDER_SUBSCRIPTION_ID = "5428138fbe6b48a5bb8c7a4f48522b01"


def _run(statement: str, **params: object) -> None:
    op.get_context().connection.execute(sa.text(statement), params)


def upgrade() -> None:
    _run(
        """
        UPDATE subscriptions
        SET plan_code = 'premium',
            status = 'active',
            billing_cycle = 'monthly',
            trial_ends_at = NULL,
            canceled_at = NULL,
            updated_at = CURRENT_TIMESTAMP
        WHERE user_id IN (
            SELECT id FROM users WHERE id = :founder_user_id
        )
        """,
        founder_user_id=_FOUNDER_USER_ID,
    )
    _run(
        """
        INSERT INTO subscriptions (
            id,
            user_id,
            plan_code,
            status,
            billing_cycle,
            created_at,
            updated_at
        )
        SELECT
            :subscription_id,
            users.id,
            'premium',
            'active',
            'monthly',
            CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP
        FROM users
        WHERE users.id = :founder_user_id
          AND NOT EXISTS (
              SELECT 1 FROM subscriptions WHERE subscriptions.user_id = users.id
          )
        """,
        founder_user_id=_FOUNDER_USER_ID,
        subscription_id=_FOUNDER_SUBSCRIPTION_ID,
    )

    for feature_key in _PREMIUM_FEATURES:
        _run(
            """
            UPDATE entitlements
            SET source = 'subscription',
                expires_at = NULL,
                granted_at = CURRENT_TIMESTAMP
            WHERE feature_key = :feature_key
              AND user_id IN (
                  SELECT id FROM users WHERE id = :founder_user_id
              )
            """,
            founder_user_id=_FOUNDER_USER_ID,
            feature_key=feature_key,
        )
        _run(
            """
            INSERT INTO entitlements (
                id,
                user_id,
                feature_key,
                source,
                granted_at,
                created_at
            )
            SELECT
                :entitlement_id,
                users.id,
                :feature_key,
                'subscription',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM users
            WHERE users.id = :founder_user_id
              AND NOT EXISTS (
                  SELECT 1
                  FROM entitlements
                  WHERE entitlements.user_id = users.id
                    AND entitlements.feature_key = :feature_key
              )
            """,
            entitlement_id=str(uuid.uuid4()),
            founder_user_id=_FOUNDER_USER_ID,
            feature_key=feature_key,
        )

    _run(
        """
        UPDATE users
        SET entitlements_version = COALESCE(entitlements_version, 0) + 1
        WHERE id = :founder_user_id
        """,
        founder_user_id=_FOUNDER_USER_ID,
    )


def downgrade() -> None:
    # Deliberately non-destructive: reverting this migration must not downgrade a
    # founder account that may have become legitimately paid after deployment.
    pass
