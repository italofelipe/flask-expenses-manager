"""Tests for FailoverLoginAttemptStorage (issue #1050)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from app.services.login_attempt_guard_storage import (
    FailoverLoginAttemptStorage,
    LoginAttemptState,
    RedisLoginAttemptStorage,
)


def _make_redis_storage() -> tuple[RedisLoginAttemptStorage, MagicMock]:
    client = MagicMock()
    client.hgetall.return_value = {}
    storage = RedisLoginAttemptStorage(client)
    return storage, client


def _make_failover(
    probe_interval: int = 60,
) -> tuple[FailoverLoginAttemptStorage, MagicMock]:
    redis_storage, client = _make_redis_storage()
    failover = FailoverLoginAttemptStorage(
        redis=redis_storage,
        probe_interval_seconds=probe_interval,
    )
    return failover, client


def _state(failures: int = 1) -> LoginAttemptState:
    return LoginAttemptState(
        failures=failures, blocked_until=0.0, updated_at=time.time()
    )


# ── Normal (Redis healthy) path ───────────────────────────────────────────────


class TestFailoverNormalPath:
    def test_get_delegates_to_redis(self) -> None:
        failover, client = _make_failover()
        client.hgetall.return_value = {
            b"failures": b"3",
            b"blocked_until": b"0.0",
            b"updated_at": b"1.0",
        }
        result = failover.get("somekey")
        assert result is not None
        assert result.failures == 3
        assert not failover.is_using_fallback

    def test_set_delegates_to_redis(self) -> None:
        failover, client = _make_failover()
        failover.set("k", _state(), ttl_seconds=300)
        client.hset.assert_called_once()
        assert not failover.is_using_fallback

    def test_delete_delegates_to_redis(self) -> None:
        failover, client = _make_failover()
        failover.delete("k")
        client.delete.assert_called_once()
        assert not failover.is_using_fallback

    def test_prune_delegates_to_redis(self) -> None:
        failover, client = _make_failover()
        # Redis prune is a no-op — just verifying no exception
        failover.prune(now=time.time(), retention_seconds=3600, max_keys=10000)
        assert not failover.is_using_fallback


# ── Failover activation ───────────────────────────────────────────────────────


class TestFailoverActivation:
    def test_get_activates_fallback_on_redis_error(self) -> None:
        failover, client = _make_failover()
        client.hgetall.side_effect = RuntimeError("redis down")
        result = failover.get("k")
        assert result is None
        assert failover.is_using_fallback

    def test_set_activates_fallback_on_redis_error(self) -> None:
        failover, client = _make_failover()
        client.hset.side_effect = RuntimeError("redis down")
        failover.set("k", _state(), ttl_seconds=300)
        assert failover.is_using_fallback

    def test_delete_activates_fallback_on_redis_error(self) -> None:
        failover, client = _make_failover()
        client.delete.side_effect = RuntimeError("redis down")
        failover.delete("k")
        assert failover.is_using_fallback

    def test_fallback_preserves_state_set_after_activation(self) -> None:
        failover, client = _make_failover()
        client.hset.side_effect = RuntimeError("redis down")
        state = _state(failures=3)
        failover.set("mykey", state, ttl_seconds=300)
        assert failover.is_using_fallback
        # State should be in memory now
        retrieved = failover.get("mykey")
        assert retrieved is not None
        assert retrieved.failures == 3

    def test_get_uses_memory_when_already_on_fallback(self) -> None:
        failover, client = _make_failover()
        # Activate fallback
        client.hset.side_effect = RuntimeError("redis down")
        failover.set("k", _state(2), ttl_seconds=300)
        assert failover.is_using_fallback
        # Subsequent get should hit memory, not Redis
        client.hgetall.reset_mock()
        result = failover.get("k")
        client.hgetall.assert_not_called()
        assert result is not None
        assert result.failures == 2

    def test_set_uses_memory_when_on_fallback(self) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        failover.set("k", _state(5), ttl_seconds=300)
        client.hset.assert_not_called()
        assert failover._memory.get("k") is not None

    def test_delete_uses_memory_when_on_fallback(self) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        failover._memory.set("k", _state(), ttl_seconds=300)
        failover.delete("k")
        assert failover._memory.get("k") is None
        client.delete.assert_not_called()

    def test_prune_uses_memory_when_on_fallback(self) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        # Should call memory prune (which caps at _FAILOVER_MAX_MEMORY_KEYS)
        failover.prune(now=time.time(), retention_seconds=3600, max_keys=100)
        # No exception — success


# ── Probe thread and recovery ─────────────────────────────────────────────────


class TestFailoverRecovery:
    def test_probe_thread_started_on_fallback_activation(self) -> None:
        failover, client = _make_failover(probe_interval=60)
        client.hset.side_effect = RuntimeError("redis down")
        failover.set("k", _state(), ttl_seconds=300)
        assert failover._probe_thread is not None
        assert failover._probe_thread.is_alive()

    def test_flush_to_redis_copies_memory_state(self) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        failover._memory.set("k1", _state(2), ttl_seconds=300)
        failover._memory.set("k2", _state(4), ttl_seconds=300)
        failover._flush_to_redis()
        assert client.hset.call_count == 2
        # Memory cleared after flush
        assert failover._memory.get("k1") is None
        assert failover._memory.get("k2") is None

    def test_flush_to_redis_skips_failed_keys(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        failover._memory.set("k1", _state(1), ttl_seconds=300)
        client.hset.side_effect = RuntimeError("still down")
        with caplog.at_level("WARNING", logger="auraxis.login_guard"):
            failover._flush_to_redis()
        assert "flush failed" in caplog.text

    def test_recovery_restores_primary_backend(self) -> None:
        failover, client = _make_failover(probe_interval=1)
        # Activate fallback
        client.hset.side_effect = RuntimeError("redis down")
        failover.set("k", _state(), ttl_seconds=300)
        assert failover.is_using_fallback

        # Simulate Redis recovering: ping succeeds, hset succeeds again
        client.ping.return_value = True
        client.hset.side_effect = None

        # Wait for probe thread to detect recovery (probe_interval=1s)
        deadline = time.time() + 5
        while failover.is_using_fallback and time.time() < deadline:
            time.sleep(0.1)

        assert not failover.is_using_fallback, "Guard should have recovered"

    def test_recovery_does_not_restore_if_flush_fails(self) -> None:
        failover, client = _make_failover(probe_interval=1)
        # Activate fallback and store state in memory so flush has entries
        client.hset.side_effect = RuntimeError("down")
        failover.set("k", _state(3), ttl_seconds=300)
        assert failover.is_using_fallback
        assert failover._memory.get("k") is not None  # entry in memory

        # Ping succeeds but hset still fails (flush will fail)
        client.ping.return_value = True
        # hset is still raising

        # Give probe thread time to try — it should NOT restore
        time.sleep(2.5)
        assert failover.is_using_fallback, "Should remain on fallback if flush fails"


# ── reset_for_tests ───────────────────────────────────────────────────────────


class TestFailoverReset:
    def test_reset_clears_fallback_flag(self) -> None:
        failover, client = _make_failover()
        failover._using_fallback = True
        failover._memory.set("k", _state(), ttl_seconds=300)
        failover.reset_for_tests()
        assert not failover.is_using_fallback
        assert failover._memory.get("k") is None

    def test_reset_stops_counting_as_fallback(self) -> None:
        failover, client = _make_failover()
        client.hset.side_effect = RuntimeError("down")
        failover.set("k", _state(), ttl_seconds=300)
        assert failover.is_using_fallback
        failover.reset_for_tests()
        assert not failover.is_using_fallback
