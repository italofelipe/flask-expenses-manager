from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class LoginAttemptContext:
    principal: str
    client_ip: str
    user_agent: str
    known_principal: bool = False

    def key(self) -> str:
        raw = f"{self.principal}|{self.client_ip}|{self.user_agent}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_bool_env(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_client_ip(
    *,
    remote_addr: str | None,
    forwarded_for: str | None,
    real_ip: str | None,
) -> str:
    trust_proxy = _read_bool_env("LOGIN_GUARD_TRUST_PROXY_HEADERS", False)
    if trust_proxy:
        forwarded = str(forwarded_for or "").strip()
        if forwarded:
            first_hop = forwarded.split(",")[0].strip()
            if first_hop:
                return first_hop
        real = str(real_ip or "").strip()
        if real:
            return real
    return str(remote_addr or "unknown")


def build_login_attempt_context(
    *,
    principal: str,
    remote_addr: str | None,
    user_agent: str | None,
    forwarded_for: str | None = None,
    real_ip: str | None = None,
    known_principal: bool = False,
) -> LoginAttemptContext:
    normalized_principal = principal.strip().lower()
    normalized_agent = str(user_agent or "").strip()[:512]
    client_ip = _resolve_client_ip(
        remote_addr=remote_addr,
        forwarded_for=forwarded_for,
        real_ip=real_ip,
    )
    return LoginAttemptContext(
        principal=normalized_principal,
        client_ip=client_ip,
        user_agent=normalized_agent,
        known_principal=known_principal,
    )


__all__ = [
    "LoginAttemptContext",
    "build_login_attempt_context",
]
