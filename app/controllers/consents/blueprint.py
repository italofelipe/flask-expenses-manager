"""Blueprint for the LGPD versioned consents REST endpoints."""

from __future__ import annotations

from flask import Blueprint

consents_bp = Blueprint("consents", __name__, url_prefix="/me/consents")
