from __future__ import annotations

from flask import Blueprint

bank_statement_bp = Blueprint(
    "bank_statement",
    __name__,
    url_prefix="/bank-statements",
)
