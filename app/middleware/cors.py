from __future__ import annotations

import os

from flask import Flask, Response, request


def _parse_allowed_origins(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {item.strip() for item in raw.split(",") if item.strip()}


def _is_allowed_origin(origin: str, allowed_origins: set[str]) -> bool:
    return "*" in allowed_origins or origin in allowed_origins


def register_cors(app: Flask) -> None:
    allowed_origins = _parse_allowed_origins(os.getenv("CORS_ALLOWED_ORIGINS"))
    app.extensions["cors_allowed_origins"] = allowed_origins

    @app.after_request  # type: ignore[misc]
    def add_cors_headers(response: Response) -> Response:
        origin = request.headers.get("Origin")
        if not origin or not _is_allowed_origin(origin, allowed_origins):
            return response

        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Vary"] = "Origin"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET,POST,PUT,PATCH,DELETE,OPTIONS"
        )
        response.headers["Access-Control-Allow-Headers"] = (
            "Authorization,Content-Type,X-API-Contract"
        )
        return response

    @app.before_request  # type: ignore[misc]
    def handle_cors_preflight() -> Response | None:
        if request.method != "OPTIONS":
            return None

        origin = request.headers.get("Origin", "")
        if not _is_allowed_origin(origin, allowed_origins):
            return None

        response = app.make_response(("", 204))
        return add_cors_headers(response)
