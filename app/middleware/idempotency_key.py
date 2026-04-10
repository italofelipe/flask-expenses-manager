"""Idempotency-Key middleware — SEC-GAP-05.

Prevents duplicate mutations caused by double-clicks or network retries.

Contract:
  - All POST requests MAY include an ``Idempotency-Key`` header.
  - POST requests to paths matching REQUIRED_PREFIXES MUST include the header
    (missing key → 400 Bad Request).
  - First request with a given key: executed normally; response is cached in
    Redis for TTL_SECONDS (24 h).
  - Subsequent requests with the same key: cached response returned as-is
    without re-executing the handler.
  - Same key + different request body: 409 Conflict.
  - Redis unavailable: middleware is bypassed (fail-open). Idempotency is best-
    effort — do NOT block requests when the backend is down.

Redis key structure:
  ``idempotency:{user_subject}:{path}:{sha256(idempotency_key_value)}``

Redis value (JSON):
  {
    "body_hash": "<sha256 of raw request body at first call>",
    "status_code": 200,
    "body": "<base64-encoded response body>",
    "content_type": "application/json",
  }

Usage:
  Register AFTER the auth guard so ``user_subject`` is available:

      from app.middleware.idempotency_key import register_idempotency_guard
      register_idempotency_guard(app)
"""

from __future__ import annotations

import base64
import hashlib
import importlib
import json
import logging
import os
from typing import Any

from flask import Flask, Response, g, jsonify, request

from app.utils.api_contract import is_v2_contract_request
from app.utils.response_builder import error_payload

logger = logging.getLogger(__name__)

TTL_SECONDS = 86_400  # 24 hours

# POST endpoints where the header is mandatory.
REQUIRED_PREFIXES = (
    "/subscriptions/checkout",
    "/subscriptions/cancel",
)

# POST endpoints that must be skipped entirely (webhooks, auth, etc.)
_SKIP_PREFIXES = (
    "/subscriptions/webhook",
    "/auth/",
    "/docs",
    "/healthz",
    "/readiness",
)

IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"
_KEY_PREFIX = "auraxis:idempotency"


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _body_hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _get_user_subject() -> str | None:
    """Return the JWT subject if a valid token is present, else None."""
    from flask_jwt_extended import get_jwt, verify_jwt_in_request
    from flask_jwt_extended.exceptions import JWTExtendedException

    try:
        verify_jwt_in_request(optional=True)
        claims = get_jwt()
        subject = claims.get("sub")
        return str(subject).strip() if subject else None
    except (JWTExtendedException, Exception):
        return None


def _build_redis_key(user_subject: str | None, path: str, idempotency_key: str) -> str:
    scope = user_subject or "anon"
    key_hash = _sha256(idempotency_key)
    return f"{_KEY_PREFIX}:{scope}:{path}:{key_hash}"


def _build_conflict_response() -> Response:
    if is_v2_contract_request():
        payload = error_payload(
            message="Idempotency-Key já utilizada com um corpo de request diferente.",
            code="IDEMPOTENCY_CONFLICT",
        )
    else:
        payload = {
            "message": (
                "Conflict: same Idempotency-Key used with a different request body."
            ),
            "error": "IDEMPOTENCY_CONFLICT",
        }
    response = jsonify(payload)
    response.status_code = 409
    return response


def _build_missing_key_response() -> Response:
    if is_v2_contract_request():
        payload = error_payload(
            message="Header Idempotency-Key obrigatório para este endpoint.",
            code="IDEMPOTENCY_KEY_REQUIRED",
        )
    else:
        payload = {
            "message": "Idempotency-Key header is required for this endpoint.",
            "error": "IDEMPOTENCY_KEY_REQUIRED",
        }
    response = jsonify(payload)
    response.status_code = 400
    return response


def _try_get_redis() -> Any | None:
    redis_url = str(
        os.getenv("IDEMPOTENCY_REDIS_URL", os.getenv("RATE_LIMIT_REDIS_URL", ""))
    ).strip()
    if not redis_url:
        return None
    try:
        redis_mod = importlib.import_module("redis")
        client = redis_mod.Redis.from_url(redis_url)
        client.ping()
        return client
    except Exception:
        return None


def _should_skip(path: str) -> bool:
    for prefix in _SKIP_PREFIXES:
        if path == prefix or path.startswith(prefix):
            return True
    return False


def _make_before_request(redis_client: Any) -> Any:
    def idempotency_before_request() -> Response | None:
        if request.method != "POST":
            return None
        if _should_skip(request.path):
            return None
        return _check_idempotency(redis_client)

    return idempotency_before_request


def _check_idempotency(redis_client: Any) -> Response | None:
    idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER, "").strip()

    is_required = any(
        request.path == p or request.path.startswith(p) for p in REQUIRED_PREFIXES
    )
    if is_required and not idempotency_key:
        return _build_missing_key_response()

    if not idempotency_key:
        return None

    user_subject = _get_user_subject()
    redis_key = _build_redis_key(user_subject, request.path, idempotency_key)
    raw_body = request.get_data()
    current_body_hash = _body_hash(raw_body)

    try:
        cached = redis_client.get(redis_key)
    except Exception:
        logger.warning("idempotency_redis_get_failed key=%s mode=fail_open", redis_key)
        return None

    if cached is None:
        g.idempotency_redis_key = redis_key
        g.idempotency_body_hash = current_body_hash
        return None

    return _replay_or_conflict(cached, current_body_hash)


def _replay_or_conflict(cached: bytes, current_body_hash: str) -> Response | None:
    try:
        stored: dict[str, Any] = json.loads(cached)
    except (json.JSONDecodeError, TypeError):
        logger.warning("idempotency_cache_corrupt")
        return None

    stored_body_hash = stored.get("body_hash", "")
    if stored_body_hash and stored_body_hash != current_body_hash:
        return _build_conflict_response()

    body_bytes = base64.b64decode(stored.get("body", ""))
    response = Response(
        body_bytes,
        status=int(stored.get("status_code", 200)),
        content_type=stored.get("content_type", "application/json"),
    )
    response.headers["X-Idempotency-Replayed"] = "true"
    return response


def _make_after_request(redis_client: Any) -> Any:
    def idempotency_after_request(response: Response) -> Response:
        redis_key = getattr(g, "idempotency_redis_key", None)
        if not redis_key:
            return response

        body_hash = getattr(g, "idempotency_body_hash", "")
        try:
            stored = json.dumps(
                {
                    "body_hash": body_hash,
                    "status_code": response.status_code,
                    "body": base64.b64encode(response.get_data()).decode(),
                    "content_type": response.content_type or "application/json",
                }
            )
            redis_client.set(redis_key, stored, ex=TTL_SECONDS)
        except Exception:
            logger.warning("idempotency_redis_set_failed key=%s", redis_key)

        return response

    return idempotency_after_request


def register_idempotency_guard(app: Flask) -> None:
    redis_client = _try_get_redis()
    if redis_client is None:
        logger.warning(
            "idempotency_guard_disabled reason=redis_unavailable mode=fail_open"
        )
        return

    app.extensions["idempotency_redis"] = redis_client
    app.before_request(_make_before_request(redis_client))
    app.after_request(_make_after_request(redis_client))
