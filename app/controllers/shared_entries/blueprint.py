from __future__ import annotations

from flask import Blueprint

shared_entries_bp = Blueprint("shared_entries", __name__, url_prefix="/shared-entries")
