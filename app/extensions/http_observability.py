from __future__ import annotations

from flask import Flask, Response, current_app

from app.extensions.integration_metrics import increment_metric, record_metric_sample
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


def _record_graphql_http_metrics(
    *, operation_name: str | None, root_fields: tuple[str, ...]
) -> None:
    if operation_name or root_fields:
        increment_metric("http.request.graphql")
    if operation_name:
        increment_metric(
            f"http.request.graphql.operation.{_metric_suffix(operation_name)}"
        )
    for root_field in root_fields:
        increment_metric(
            f"http.request.graphql.root_field.{_metric_suffix(root_field)}"
        )


def register_http_observability(app: Flask) -> None:
    @app.before_request
    def _mark_request_start() -> None:
        mark_request_start()

    def _emit_observability(response: Response) -> None:
        envelope = build_observability_envelope(response)
        if envelope is None:
            return

        increment_metric("http.request.total")
        increment_metric(f"http.request.framework.{envelope.source_framework}")
        increment_metric(f"http.request.status.{envelope.status_code}")
        increment_metric(
            f"http.request.method.{_metric_suffix(envelope.method)}",
        )
        increment_metric(
            f"http.request.route.{_metric_suffix(envelope.route)}",
        )
        increment_metric(
            f"http.request.status_class.{_metric_suffix(envelope.status_class)}",
        )
        increment_metric("http.request.duration_ms_total", amount=envelope.duration_ms)
        record_metric_sample(
            f"http.route.duration_ms.{envelope.route}",
            envelope.duration_ms,
        )
        if envelope.is_error:
            increment_metric("http.request.error")
        if envelope.trace_id:
            increment_metric("http.request.trace.present")
        else:
            increment_metric("http.request.trace.absent")
        _record_graphql_http_metrics(
            operation_name=envelope.graphql_operation_name,
            root_fields=envelope.graphql_root_fields,
        )
        if envelope.auth_subject:
            increment_metric("http.request.authenticated")
        else:
            increment_metric("http.request.anonymous")

        current_app.logger.info(format_observability_log(envelope))

    @app.after_request
    def _record_observability(response: Response) -> Response:  # NOSONAR
        # Flask after_request handlers must return the response object they receive.
        _emit_observability(response)
        return response


__all__ = ["register_http_observability"]
