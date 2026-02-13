"""Transaction controller compatibility facade.

This module preserves legacy imports while routing endpoint registration to the
modular transaction package.
"""

from __future__ import annotations

from app.controllers.transaction import TransactionResource, transaction_bp
from app.controllers.transaction.utils import (
    _build_installment_amounts,
    _guard_revoked_token,
)
from app.extensions.jwt_callbacks import is_token_revoked

__all__ = [
    "transaction_bp",
    "TransactionResource",
    "_guard_revoked_token",
    "_build_installment_amounts",
    "is_token_revoked",
]
