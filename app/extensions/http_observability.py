from __future__ import annotations

from flask import Flask, Response, current_app

from app.extensions.integration_metrics import increment_metric
from app.http import (
    build_observability_envelope,
    format_observability_log,
    mark_request_start,
)


def _metric_suffix(value: str) -> str:
    normalized = "".join(
        character.lower() if character.isalnum() else "_" for character in value.strip()
    ).strip("_")
    return normalized or "unknown"


def register_http_observability(app: Flask) -> None:
    @app.before_request
    def _mark_request_start() -> None:
        mark_request_start()

    @app.after_request
    def _record_observability(response: Response) -> Response:
        envelope = build_observability_envelope(response)
        if envelope is None:
            return response

        increment_metric("http.request.total")
        increment_metric(f"http.request.framework.{envelope.source_framework}")
        increment_metric(f"http.request.status.{envelope.status_code}")
        increment_metric(
            f"http.request.method.{_metric_suffix(envelope.method)}",
        )
        increment_metric(
            f"http.request.route.{_metric_suffix(envelope.route)}",
        )
        increment_metric("http.request.duration_ms_total", amount=envelope.duration_ms)
        if envelope.auth_subject:
            increment_metric("http.request.authenticated")
        else:
            increment_metric("http.request.anonymous")

        current_app.logger.info(format_observability_log(envelope))
        return response


__all__ = ["register_http_observability"]
