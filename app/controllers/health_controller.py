"""
Health endpoints.

Why this exists
- Infra (Docker, reverse proxy, load balancers, canaries) needs a stable and
  public liveness endpoint that does not require authentication.
- We intentionally keep this lightweight (no DB check by default) to avoid
  cascading failures during partial outages.

Contract
- `GET /healthz` returns HTTP 200 with a minimal JSON body.
"""

from __future__ import annotations

from flask import Blueprint, Response, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/healthz")
def healthz() -> tuple[Response, int]:
    """Liveness probe endpoint (public)."""

    return jsonify({"status": "ok"}), 200
