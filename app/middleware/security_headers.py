from __future__ import annotations

import os
from dataclasses import dataclass

from flask import Flask, Request, Response, request


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class SecurityHeadersPolicy:
    frame_options: str
    content_type_options: str
    referrer_policy: str
    permissions_policy: str
    hsts_value: str
    hsts_enabled: bool


def _build_security_headers_policy() -> SecurityHeadersPolicy:
    is_debug = _read_bool_env("FLASK_DEBUG", False)
    is_testing = _read_bool_env("FLASK_TESTING", False)
    is_production = not (is_debug or is_testing)
    return SecurityHeadersPolicy(
        frame_options=os.getenv("SECURITY_X_FRAME_OPTIONS", "SAMEORIGIN").strip(),
        content_type_options=os.getenv(
            "SECURITY_X_CONTENT_TYPE_OPTIONS",
            "nosniff",
        ).strip(),
        referrer_policy=os.getenv(
            "SECURITY_REFERRER_POLICY",
            "strict-origin-when-cross-origin",
        ).strip(),
        permissions_policy=os.getenv(
            "SECURITY_PERMISSIONS_POLICY",
            "geolocation=(), microphone=(), camera=()",
        ).strip(),
        hsts_value=os.getenv(
            "SECURITY_HSTS_VALUE",
            "max-age=31536000; includeSubDomains",
        ).strip(),
        hsts_enabled=_read_bool_env("SECURITY_HSTS_ENABLED", is_production),
    )


def _is_secure_request(current_request: Request) -> bool:
    if current_request.is_secure:
        return True
    forwarded_proto = str(current_request.headers.get("X-Forwarded-Proto", "")).lower()
    return forwarded_proto == "https"


def register_security_headers(app: Flask) -> None:
    policy = _build_security_headers_policy()
    app.extensions["security_headers_policy"] = policy

    @app.after_request
    def attach_security_headers(response: Response) -> Response:
        response.headers["X-Frame-Options"] = policy.frame_options
        response.headers["X-Content-Type-Options"] = policy.content_type_options
        response.headers["Referrer-Policy"] = policy.referrer_policy
        response.headers["Permissions-Policy"] = policy.permissions_policy
        if policy.hsts_enabled and _is_secure_request(request):
            response.headers["Strict-Transport-Security"] = policy.hsts_value
        return response
