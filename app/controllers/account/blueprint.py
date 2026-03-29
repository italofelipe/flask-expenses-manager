from __future__ import annotations

from flask import Blueprint

account_bp = Blueprint("account", __name__, url_prefix="/accounts")
