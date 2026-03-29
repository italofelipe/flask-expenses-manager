from __future__ import annotations

from flask import Blueprint

credit_card_bp = Blueprint("credit_card", __name__, url_prefix="/credit-cards")
