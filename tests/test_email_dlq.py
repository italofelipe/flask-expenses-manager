"""Tests for EmailDLQ (issue #1049)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.email_dlq import (
    RedisEmailDLQ,
    _build_dlq,
    _NoOpEmailDLQ,
    reset_email_dlq_for_tests,
)
from app.services.email_provider import (
    EmailDeliveryResult,
    EmailMessage,
    EmailProviderError,
)


@pytest.fixture(autouse=True)
def _reset_dlq_singleton():
    reset_email_dlq_for_tests()
    yield
    reset_email_dlq_for_tests()


def _make_message(**kwargs: str) -> EmailMessage:
    defaults = dict(
        to_email="user@example.com",
        subject="Test Subject",
        html="<p>Hello</p>",
        text="Hello",
        tag="test",
    )
    defaults.update(kwargs)
    return EmailMessage(**defaults)  # type: ignore[arg-type]


# ── _NoOpEmailDLQ ─────────────────────────────────────────────────────────────


class TestNoOpEmailDLQ:
    def test_push_logs_error(self, caplog: pytest.LogCaptureFixture) -> None:
        dlq = _NoOpEmailDLQ()
        with caplog.at_level("ERROR", logger="auraxis.email_dlq"):
            dlq.push(_make_message(), reason="provider down")
        assert "email LOST" in caplog.text

    def test_retry_returns_zero(self) -> None:
        assert _NoOpEmailDLQ().retry_pending(limit=10) == 0

    def test_list_returns_empty(self) -> None:
        assert _NoOpEmailDLQ().list_pending() == []

    def test_size_returns_zero(self) -> None:
        assert _NoOpEmailDLQ().size() == 0

    def test_not_available(self) -> None:
        assert not _NoOpEmailDLQ().available


# ── RedisEmailDLQ ─────────────────────────────────────────────────────────────


def _make_redis_dlq() -> tuple[RedisEmailDLQ, MagicMock]:
    client = MagicMock()
    client.llen.return_value = 0
    client.lrange.return_value = []
    dlq = RedisEmailDLQ(client)
    return dlq, client


class TestRedisEmailDLQ:
    def test_push_enqueues_json(self) -> None:
        dlq, client = _make_redis_dlq()
        msg = _make_message()
        dlq.push(msg, reason="test failure")
        assert client.rpush.called
        raw = client.rpush.call_args[0][1]
        import json

        data = json.loads(raw)
        assert data["to_email"] == "user@example.com"
        assert data["reason"] == "test failure"
        assert "enqueued_at" in data
        # html/text are stored in push (needed for retry)
        assert data["html"] == "<p>Hello</p>"

    def test_push_trims_list(self) -> None:
        dlq, client = _make_redis_dlq()
        dlq.push(_make_message(), reason="x")
        client.ltrim.assert_called_once_with("auraxis:email:dlq", -1000, -1)

    def test_size_delegates_to_llen(self) -> None:
        dlq, client = _make_redis_dlq()
        client.llen.return_value = 7
        assert dlq.size() == 7

    def test_is_available(self) -> None:
        dlq, _ = _make_redis_dlq()
        assert dlq.available

    def test_list_pending_redacts_html_text(self) -> None:
        import json as _json

        dlq, client = _make_redis_dlq()
        entry = dict(
            to_email="a@b.com",
            subject="Hi",
            html="<p>big html</p>",
            text="big text",
            tag="t",
            reason="r",
            enqueued_at=1.0,
        )
        client.lrange.return_value = [_json.dumps(entry).encode()]
        result = dlq.list_pending()
        assert len(result) == 1
        assert "html" not in result[0]
        assert "text" not in result[0]
        assert result[0]["to_email"] == "a@b.com"

    def test_retry_delivers_and_removes(self) -> None:
        import json as _json

        dlq, client = _make_redis_dlq()
        entry = dict(
            to_email="a@b.com",
            subject="Hi",
            html="<p>x</p>",
            text="x",
            tag="t",
            reason="r",
            enqueued_at=1.0,
        )
        raw = _json.dumps(entry).encode()
        client.lrange.return_value = [raw]

        mock_provider = MagicMock()
        mock_provider.send.return_value = EmailDeliveryResult(provider="resend")

        with patch(
            "app.services.email_provider.get_default_email_provider",
            return_value=mock_provider,
        ):
            delivered = dlq.retry_pending(limit=10)

        assert delivered == 1
        mock_provider.send.assert_called_once()
        client.lrem.assert_called_with("auraxis:email:dlq", 1, raw)

    def test_retry_requeues_on_failure(self) -> None:
        import json as _json

        dlq, client = _make_redis_dlq()
        entry = dict(
            to_email="a@b.com",
            subject="Hi",
            html="<p>x</p>",
            text="x",
            tag="t",
            reason="original",
            enqueued_at=1.0,
        )
        raw = _json.dumps(entry).encode()
        client.lrange.return_value = [raw]

        mock_provider = MagicMock()
        mock_provider.send.side_effect = EmailProviderError("still down")

        with patch(
            "app.services.email_provider.get_default_email_provider",
            return_value=mock_provider,
        ):
            delivered = dlq.retry_pending(limit=10)

        assert delivered == 0
        # Old entry removed, new entry pushed with updated reason
        assert client.lrem.called
        assert client.rpush.called
        new_raw = client.rpush.call_args[0][1]
        new_entry = _json.loads(new_raw)
        assert "retry_failed" in new_entry["reason"]

    def test_retry_skips_corrupt_entries(self) -> None:
        dlq, client = _make_redis_dlq()
        client.lrange.return_value = [b"not valid json"]

        mock_provider = MagicMock()
        with patch(
            "app.services.email_provider.get_default_email_provider",
            return_value=mock_provider,
        ):
            delivered = dlq.retry_pending(limit=10)

        assert delivered == 0
        mock_provider.send.assert_not_called()
        # Corrupt entry removed from queue
        client.lrem.assert_called_with("auraxis:email:dlq", 1, b"not valid json")

    def test_push_redis_error_logs_and_does_not_raise(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        dlq, client = _make_redis_dlq()
        client.rpush.side_effect = RuntimeError("redis down")
        with caplog.at_level("ERROR", logger="auraxis.email_dlq"):
            # Must not raise
            dlq.push(_make_message(), reason="x")
        assert "email LOST" in caplog.text


# ── _build_dlq factory ────────────────────────────────────────────────────────


class TestBuildDlq:
    def test_no_redis_url_returns_noop(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("REDIS_URL", raising=False)
        dlq = _build_dlq()
        assert isinstance(dlq, _NoOpEmailDLQ)

    def test_redis_connection_failure_returns_noop(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("REDIS_URL", "redis://localhost:9999")
        dlq = _build_dlq()
        assert isinstance(dlq, _NoOpEmailDLQ)


# ── ResendEmailProvider.send_with_dlq_fallback ────────────────────────────────


class TestSendWithDlqFallback:
    def test_success_does_not_push_to_dlq(self) -> None:
        from app.services.email_provider import ResendEmailProvider

        provider = ResendEmailProvider.__new__(ResendEmailProvider)
        msg = _make_message()

        mock_dlq = MagicMock()
        with (
            patch.object(
                provider,
                "send",
                return_value=EmailDeliveryResult(provider="resend"),
            ),
            patch("app.services.email_dlq.get_email_dlq", return_value=mock_dlq),
        ):
            result = provider.send_with_dlq_fallback(msg)

        assert result.provider == "resend"
        mock_dlq.push.assert_not_called()

    def test_provider_error_pushes_to_dlq_and_reraises(self) -> None:
        from app.services.email_provider import ResendEmailProvider

        provider = ResendEmailProvider.__new__(ResendEmailProvider)
        msg = _make_message()

        mock_dlq = MagicMock()
        with (
            patch.object(provider, "send", side_effect=EmailProviderError("down")),
            patch("app.services.email_dlq.get_email_dlq", return_value=mock_dlq),
            pytest.raises(EmailProviderError),
        ):
            provider.send_with_dlq_fallback(msg)

        mock_dlq.push.assert_called_once_with(msg, reason="down")
