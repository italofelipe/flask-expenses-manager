"""Unit tests for app/services/login_attempt_guard_context.py."""

from __future__ import annotations

from app.services.login_attempt_guard_context import (
    LoginAttemptContext,
    _read_bool_env,
    _resolve_client_ip,
    build_login_attempt_context,
)


class TestReadBoolEnv:
    def test_returns_default_when_var_not_set(self, monkeypatch):
        monkeypatch.delenv("TEST_BOOL_VAR", raising=False)
        assert _read_bool_env("TEST_BOOL_VAR", False) is False
        assert _read_bool_env("TEST_BOOL_VAR", True) is True

    def test_returns_true_for_1(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "1")
        assert _read_bool_env("TEST_BOOL_VAR", False) is True

    def test_returns_true_for_true(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "true")
        assert _read_bool_env("TEST_BOOL_VAR", False) is True

    def test_returns_true_for_yes(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "yes")
        assert _read_bool_env("TEST_BOOL_VAR", False) is True

    def test_returns_true_for_on(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "on")
        assert _read_bool_env("TEST_BOOL_VAR", False) is True

    def test_returns_false_for_false(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "false")
        assert _read_bool_env("TEST_BOOL_VAR", True) is False

    def test_returns_false_for_0(self, monkeypatch):
        monkeypatch.setenv("TEST_BOOL_VAR", "0")
        assert _read_bool_env("TEST_BOOL_VAR", True) is False


class TestResolveClientIp:
    def test_returns_remote_addr_when_trust_proxy_disabled(self, monkeypatch):
        monkeypatch.delenv("LOGIN_GUARD_TRUST_PROXY_HEADERS", raising=False)
        ip = _resolve_client_ip(
            remote_addr="10.0.0.1",
            forwarded_for="192.168.1.1",
            real_ip="172.16.0.1",
        )
        assert ip == "10.0.0.1"

    def test_returns_unknown_when_no_remote_addr(self, monkeypatch):
        monkeypatch.delenv("LOGIN_GUARD_TRUST_PROXY_HEADERS", raising=False)
        ip = _resolve_client_ip(remote_addr=None, forwarded_for=None, real_ip=None)
        assert ip == "unknown"

    def test_uses_first_forwarded_for_hop_when_trust_proxy_enabled(self, monkeypatch):
        monkeypatch.setenv("LOGIN_GUARD_TRUST_PROXY_HEADERS", "true")
        ip = _resolve_client_ip(
            remote_addr="10.0.0.1",
            forwarded_for="203.0.113.5, 10.0.0.1",
            real_ip=None,
        )
        assert ip == "203.0.113.5"

    def test_uses_real_ip_when_forwarded_for_empty(self, monkeypatch):
        monkeypatch.setenv("LOGIN_GUARD_TRUST_PROXY_HEADERS", "true")
        ip = _resolve_client_ip(
            remote_addr="10.0.0.1",
            forwarded_for="",
            real_ip="198.51.100.7",
        )
        assert ip == "198.51.100.7"

    def test_falls_back_to_remote_addr_when_trust_proxy_headers_empty(
        self, monkeypatch
    ):
        monkeypatch.setenv("LOGIN_GUARD_TRUST_PROXY_HEADERS", "true")
        ip = _resolve_client_ip(
            remote_addr="10.0.0.2",
            forwarded_for="",
            real_ip="",
        )
        assert ip == "10.0.0.2"


class TestLoginAttemptContext:
    def test_key_is_deterministic(self):
        ctx = LoginAttemptContext(
            principal="user@example.com",
            client_ip="10.0.0.1",
            user_agent="Mozilla/5.0",
        )
        assert ctx.key() == ctx.key()

    def test_different_inputs_produce_different_keys(self):
        ctx1 = LoginAttemptContext(
            principal="a@example.com", client_ip="10.0.0.1", user_agent="UA1"
        )
        ctx2 = LoginAttemptContext(
            principal="b@example.com", client_ip="10.0.0.1", user_agent="UA1"
        )
        assert ctx1.key() != ctx2.key()


class TestBuildLoginAttemptContext:
    def test_normalizes_principal_to_lowercase(self):
        ctx = build_login_attempt_context(
            principal="User@Example.COM",
            remote_addr="127.0.0.1",
            user_agent="TestAgent",
        )
        assert ctx.principal == "user@example.com"

    def test_truncates_user_agent_to_512_chars(self):
        long_agent = "A" * 600
        ctx = build_login_attempt_context(
            principal="user@example.com",
            remote_addr="127.0.0.1",
            user_agent=long_agent,
        )
        assert len(ctx.user_agent) == 512

    def test_handles_none_user_agent(self):
        ctx = build_login_attempt_context(
            principal="user@example.com",
            remote_addr="127.0.0.1",
            user_agent=None,
        )
        assert ctx.user_agent == ""

    def test_known_principal_flag(self):
        ctx = build_login_attempt_context(
            principal="user@example.com",
            remote_addr="127.0.0.1",
            user_agent="UA",
            known_principal=True,
        )
        assert ctx.known_principal is True
