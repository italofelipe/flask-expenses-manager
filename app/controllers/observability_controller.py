from __future__ import annotations

import os

from flask import Blueprint, Response, jsonify, request

from app.extensions.integration_metrics import (
    build_observability_export_payload,
    build_prometheus_metrics_payload,
)
from app.extensions.prometheus_metrics import generate_latest_metrics
from app.utils.typed_decorators import typed_doc as doc

observability_bp = Blueprint("observability", __name__)
_OBSERVABILITY_TOKEN_HEADER = "X-Observability-Key"


def _observability_export_enabled() -> bool:
    return os.getenv("OBSERVABILITY_EXPORT_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _observability_export_token() -> str:
    return os.getenv("OBSERVABILITY_EXPORT_TOKEN", "").strip()


def _authorize_observability_export() -> Response | None:
    if not _observability_export_enabled():
        response = jsonify({"message": "Not Found"})
        response.status_code = 404
        return response
    configured_token = _observability_export_token()
    provided_token = request.headers.get(_OBSERVABILITY_TOKEN_HEADER, "").strip()
    if not configured_token or provided_token != configured_token:
        response = jsonify(
            {
                "message": "Unauthorized",
                "success": False,
                "error": {"code": "UNAUTHORIZED", "details": {}},
            }
        )
        response.status_code = 401
        return response
    return None


@observability_bp.get("/ops/observability")
@doc(
    description="Exporta snapshot JSON de métricas internas para collector externo.",
    tags=["Observability"],
    responses={
        200: {"description": "Snapshot JSON de observabilidade"},
        401: {"description": "Chave inválida ou ausente"},
        404: {"description": "Export desabilitado"},
    },
)
def observability_snapshot() -> Response:
    authorization_error = _authorize_observability_export()
    if authorization_error is not None:
        return authorization_error
    return jsonify(build_observability_export_payload())


@observability_bp.get("/ops/metrics")
@doc(
    description="Exporta métricas em formato texto compatível com scrape simples.",
    tags=["Observability"],
    responses={
        200: {"description": "Payload Prometheus text exposition"},
        401: {"description": "Chave inválida ou ausente"},
        404: {"description": "Export desabilitado"},
    },
)
def observability_metrics() -> Response:
    authorization_error = _authorize_observability_export()
    if authorization_error is not None:
        return authorization_error
    legacy_payload = build_prometheus_metrics_payload()
    prom_bytes, content_type = generate_latest_metrics()
    prom_text = prom_bytes.decode("utf-8") if prom_bytes else ""
    combined = (
        prom_text + ("\n" if prom_text and legacy_payload else "") + legacy_payload
    )
    return Response(combined, mimetype=content_type)


__all__ = ["observability_bp"]
