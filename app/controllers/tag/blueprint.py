from __future__ import annotations

from flask import Blueprint

tag_bp = Blueprint("tag", __name__, url_prefix="/tags")
