"""
Transaction resources compatibility facade.

This module keeps legacy import paths stable while implementation
is split into focused resource mixins.
"""

from __future__ import annotations

from flask_apispec.views import MethodResource

from .create_resource import TransactionCreateMixin
from .delete_resource import TransactionDeleteMixin
from .update_resource import TransactionUpdateMixin
from .utils import _build_installment_amounts


class TransactionResource(
    TransactionCreateMixin,
    TransactionUpdateMixin,
    TransactionDeleteMixin,
    MethodResource,
):
    """Compatibility class preserving legacy TransactionResource import path."""

    pass


__all__ = ["TransactionResource", "_build_installment_amounts"]
