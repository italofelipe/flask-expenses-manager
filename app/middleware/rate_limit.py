from __future__ import annotations

import os
import threading
from collections import defaultdict, deque
from dataclasses import dataclass
from time import monotonic, time
from typing import Any, Deque, Protocol

from flask import Flask, Response, g, jsonify, request
from flask_jwt_extended import decode_token

from app.utils.response_builder import error_payload

CONTRACT_HEADER = "X-API-Contract"
CONTRACT_V2 = "v2"
RATE_LIMIT_ERROR_CODE = "RATE_LIMIT_EXCEEDED"
RATE_LIMIT_MESSAGE = "Limite de requisições excedido. Tente novamente em instantes."

KEY_SCOPE_IP = "ip"
KEY_SCOPE_USER_OR_IP = "user_or_ip"

_SKIPPED_ENDPOINTS = {
    "static",
    "swaggerui.index",
    "swaggerui.static",
    "swaggerui.swagger_json",
    "swagger-ui",
    "swagger-ui.static",
    "swagger-ui.swagger_json",
}


def _read_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        parsed = int(raw)
    except ValueError:
        return default
    return parsed if parsed > 0 else default


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _is_v2_contract_request() -> bool:
    header_value = str(request.headers.get(CONTRACT_HEADER, "")).strip().lower()
    return header_value == CONTRACT_V2


def _get_client_ip() -> str:
    trust_proxy_headers = _read_bool_env("RATE_LIMIT_TRUST_PROXY_HEADERS", False)
    if trust_proxy_headers:
        forwarded_for = str(request.headers.get("X-Forwarded-For", "")).strip()
        if forwarded_for:
            first_hop = forwarded_for.split(",")[0].strip()
            if first_hop:
                return first_hop
        real_ip = str(request.headers.get("X-Real-IP", "")).strip()
        if real_ip:
            return real_ip
    return str(request.remote_addr or "unknown")


def _extract_subject_from_bearer_token() -> str | None:
    auth_header = str(request.headers.get("Authorization", "")).strip()
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1].strip()
    if not token:
        return None

    try:
        decoded = decode_token(token, allow_expired=False)
    except Exception:
        return None

    subject = decoded.get("sub")
    if subject is None:
        return None
    subject_str = str(subject).strip()
    return subject_str or None


@dataclass(frozen=True)
class RateLimitRule:
    name: str
    limit: int
    window_seconds: int
    key_scope: str


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    rule: RateLimitRule
    remaining: int
    retry_after_seconds: int
    key: str

    def headers(self) -> dict[str, str]:
        return {
            "X-RateLimit-Limit": str(self.rule.limit),
            "X-RateLimit-Remaining": str(self.remaining),
            "X-RateLimit-Reset": str(self.retry_after_seconds),
            "X-RateLimit-Rule": self.rule.name,
        }


class RateLimiterService:
    def __init__(
        self,
        *,
        rules: dict[str, RateLimitRule],
        storage: "RateLimitStorage",
        backend_name: str,
    ) -> None:
        self._rules = rules
        self._storage = storage
        self.backend_name = backend_name
        self._route_rule_order: tuple[tuple[str, str], ...] = (
            ("/auth/login", "auth"),
            ("/auth/register", "auth"),
            ("/graphql", "graphql"),
            ("/transactions", "transactions"),
            ("/wallet", "wallet"),
        )

    @classmethod
    def from_env(cls) -> "RateLimiterService":
        default_window = _read_int_env("RATE_LIMIT_DEFAULT_WINDOW_SECONDS", 60)
        rules = {
            "auth": RateLimitRule(
                name="auth",
                limit=_read_int_env("RATE_LIMIT_AUTH_LIMIT", 20),
                window_seconds=_read_int_env(
                    "RATE_LIMIT_AUTH_WINDOW_SECONDS", default_window
                ),
                key_scope=KEY_SCOPE_IP,
            ),
            "graphql": RateLimitRule(
                name="graphql",
                limit=_read_int_env("RATE_LIMIT_GRAPHQL_LIMIT", 120),
                window_seconds=_read_int_env(
                    "RATE_LIMIT_GRAPHQL_WINDOW_SECONDS", default_window
                ),
                key_scope=KEY_SCOPE_USER_OR_IP,
            ),
            "transactions": RateLimitRule(
                name="transactions",
                limit=_read_int_env("RATE_LIMIT_TRANSACTIONS_LIMIT", 180),
                window_seconds=_read_int_env(
                    "RATE_LIMIT_TRANSACTIONS_WINDOW_SECONDS", default_window
                ),
                key_scope=KEY_SCOPE_USER_OR_IP,
            ),
            "wallet": RateLimitRule(
                name="wallet",
                limit=_read_int_env("RATE_LIMIT_WALLET_LIMIT", 180),
                window_seconds=_read_int_env(
                    "RATE_LIMIT_WALLET_WINDOW_SECONDS", default_window
                ),
                key_scope=KEY_SCOPE_USER_OR_IP,
            ),
            "default": RateLimitRule(
                name="default",
                limit=_read_int_env("RATE_LIMIT_DEFAULT_LIMIT", 300),
                window_seconds=default_window,
                key_scope=KEY_SCOPE_USER_OR_IP,
            ),
        }
        storage, backend_name = _build_storage_from_env()
        return cls(rules=rules, storage=storage, backend_name=backend_name)

    def set_rule(
        self,
        name: str,
        *,
        limit: int | None = None,
        window_seconds: int | None = None,
    ) -> None:
        current = self._rules.get(name)
        if current is None:
            raise KeyError(f"Rate limit rule '{name}' not found.")
        resolved_limit = current.limit if limit is None else max(limit, 1)
        resolved_window = (
            current.window_seconds if window_seconds is None else max(window_seconds, 1)
        )
        self._rules[name] = RateLimitRule(
            name=current.name,
            limit=resolved_limit,
            window_seconds=resolved_window,
            key_scope=current.key_scope,
        )
        self.reset()

    def reset(self) -> None:
        self._storage.reset()

    def _resolve_rule(self, path: str) -> RateLimitRule:
        for prefix, rule_name in self._route_rule_order:
            if path == prefix or path.startswith(f"{prefix}/"):
                return self._rules[rule_name]
        return self._rules["default"]

    @staticmethod
    def _resolve_rate_limit_key(
        *,
        rule: RateLimitRule,
        user_subject: str | None,
        client_ip: str,
    ) -> str:
        if rule.key_scope == KEY_SCOPE_IP:
            return f"ip:{client_ip}"
        if user_subject:
            return f"user:{user_subject}"
        return f"ip:{client_ip}"

    def consume(
        self,
        *,
        path: str,
        user_subject: str | None,
        client_ip: str,
    ) -> RateLimitDecision:
        rule = self._resolve_rule(path)
        key = self._resolve_rate_limit_key(
            rule=rule,
            user_subject=user_subject,
            client_ip=client_ip,
        )
        consumed, retry_after_seconds = self._storage.consume(
            rule_name=rule.name,
            key=key,
            window_seconds=rule.window_seconds,
        )
        allowed = consumed <= rule.limit
        remaining = max(rule.limit - min(consumed, rule.limit), 0)
        return RateLimitDecision(
            allowed=allowed,
            rule=rule,
            remaining=remaining,
            retry_after_seconds=max(1, retry_after_seconds),
            key=key,
        )


class RateLimitStorage(Protocol):
    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        pass

    def reset(self) -> None:
        pass


class InMemoryRateLimitStorage:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        now = monotonic()
        bucket_key = (rule_name, key)
        with self._lock:
            events = self._events[bucket_key]
            cutoff = now - window_seconds
            while events and events[0] <= cutoff:
                events.popleft()
            events.append(now)
            retry_after_seconds = max(1, int(window_seconds - (now - events[0])))
            return len(events), retry_after_seconds

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


class RedisRateLimitStorage:
    def __init__(self, client: Any, *, key_prefix: str = "auraxis:rate-limit") -> None:
        self._client = client
        self._key_prefix = key_prefix

    def _window_slot(self, window_seconds: int) -> tuple[int, int]:
        now_seconds = int(time())
        slot = now_seconds // window_seconds
        retry_after_seconds = max(1, window_seconds - (now_seconds % window_seconds))
        return slot, retry_after_seconds

    def consume(
        self,
        *,
        rule_name: str,
        key: str,
        window_seconds: int,
    ) -> tuple[int, int]:
        slot, retry_after_seconds = self._window_slot(window_seconds)
        redis_key = f"{self._key_prefix}:{rule_name}:{key}:{slot}"
        consumed = int(self._client.incr(redis_key))
        if consumed == 1:
            self._client.expire(redis_key, window_seconds + 2)
        return consumed, retry_after_seconds

    def reset(self) -> None:
        # No-op for Redis backend in runtime paths.
        # Keys expire naturally by TTL.
        return None


def _build_storage_from_env() -> tuple[RateLimitStorage, str]:
    backend = str(os.getenv("RATE_LIMIT_BACKEND", "memory")).strip().lower()
    if backend != "redis":
        return InMemoryRateLimitStorage(), "memory"

    redis_url = str(
        os.getenv("RATE_LIMIT_REDIS_URL", os.getenv("REDIS_URL", ""))
    ).strip()
    if not redis_url:
        return InMemoryRateLimitStorage(), "memory"

    try:
        import redis  # type: ignore[import-untyped]
    except Exception:
        return InMemoryRateLimitStorage(), "memory"

    try:
        client = redis.Redis.from_url(redis_url)
        client.ping()
    except Exception:
        return InMemoryRateLimitStorage(), "memory"
    return RedisRateLimitStorage(client), "redis"


def _build_rate_limited_response(decision: RateLimitDecision) -> Response:
    details = {
        "rule": decision.rule.name,
        "limit": decision.rule.limit,
        "window_seconds": decision.rule.window_seconds,
        "retry_after_seconds": decision.retry_after_seconds,
    }
    if _is_v2_contract_request():
        payload = error_payload(
            message=RATE_LIMIT_MESSAGE,
            code=RATE_LIMIT_ERROR_CODE,
            details=details,
        )
    else:
        payload = {
            "message": "Too many requests",
            "error": RATE_LIMIT_ERROR_CODE,
            "details": details,
        }

    response = jsonify(payload)
    response.status_code = 429
    for header_name, header_value in decision.headers().items():
        response.headers[header_name] = header_value
    response.headers["Retry-After"] = str(decision.retry_after_seconds)
    return response


def register_rate_limit_guard(app: Flask) -> None:
    if not _read_bool_env("RATE_LIMIT_ENABLED", True):
        return

    limiter = RateLimiterService.from_env()
    app.extensions["rate_limiter"] = limiter

    def rate_limit_guard() -> Response | None:
        if request.method == "OPTIONS":
            return None
        if request.path.startswith("/docs"):
            return None
        if request.endpoint in _SKIPPED_ENDPOINTS:
            return None

        decision = limiter.consume(
            path=request.path,
            user_subject=_extract_subject_from_bearer_token(),
            client_ip=_get_client_ip(),
        )
        g.rate_limit_headers = decision.headers()

        if decision.allowed:
            return None
        return _build_rate_limited_response(decision)

    def attach_rate_limit_headers(response: Response) -> Response:
        headers = getattr(g, "rate_limit_headers", None)
        if isinstance(headers, dict):
            for header_name, header_value in headers.items():
                response.headers[header_name] = str(header_value)
        return response

    app.before_request(rate_limit_guard)
    app.after_request(attach_rate_limit_headers)
