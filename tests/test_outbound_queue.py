"""Tests for the OutboundQueue port and its adapters (ARC-API-02)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.outbound_queue import (
    OutboundQueue,
    RQOutboundQueue,
    SyncOutboundQueue,
    get_default_outbound_queue,
    reset_outbound_queue_for_tests,
)


@pytest.fixture(autouse=True)
def _reset_singleton():
    reset_outbound_queue_for_tests()
    yield
    reset_outbound_queue_for_tests()


class TestOutboundQueueProtocol:
    def test_sync_satisfies_protocol(self):
        assert isinstance(SyncOutboundQueue(), OutboundQueue)

    def test_factory_returns_sync_when_no_redis_url(self):
        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("REDIS_URL", None)
            queue = get_default_outbound_queue()
            assert isinstance(queue, SyncOutboundQueue)

    def test_factory_is_singleton(self):
        q1 = get_default_outbound_queue()
        q2 = get_default_outbound_queue()
        assert q1 is q2

    def test_reset_clears_singleton(self):
        q1 = get_default_outbound_queue()
        reset_outbound_queue_for_tests()
        q2 = get_default_outbound_queue()
        assert q1 is not q2

    def test_factory_falls_back_to_sync_when_redis_unavailable(self):
        with patch.dict("os.environ", {"REDIS_URL": "redis://localhost:19999/0"}):
            reset_outbound_queue_for_tests()
            queue = get_default_outbound_queue()
            assert isinstance(queue, SyncOutboundQueue)


class TestSyncOutboundQueue:
    _EMAIL_KWARGS = dict(
        to_email="user@example.com",
        subject="Test",
        html="<p>Hi</p>",
        text="Hi",
        tag="test_tag",
    )

    def test_enqueue_calls_email_provider(self, app):
        mock_provider = MagicMock()
        with app.app_context():
            with patch(
                "app.services.email_provider.get_default_email_provider",
                return_value=mock_provider,
            ):
                SyncOutboundQueue().enqueue_send_email(**self._EMAIL_KWARGS)
        mock_provider.send.assert_called_once()
        sent_msg = mock_provider.send.call_args[0][0]
        assert sent_msg.to_email == "user@example.com"
        assert sent_msg.tag == "test_tag"

    def test_enqueue_pushes_to_dlq_on_provider_failure(self, app):
        mock_provider = MagicMock()
        mock_provider.send.side_effect = Exception("Resend 503")
        mock_dlq = MagicMock()
        with app.app_context():
            with (
                patch(
                    "app.services.email_provider.get_default_email_provider",
                    return_value=mock_provider,
                ),
                patch(
                    "app.services.email_dlq.get_email_dlq",
                    return_value=mock_dlq,
                ),
            ):
                SyncOutboundQueue().enqueue_send_email(**self._EMAIL_KWARGS)
        mock_dlq.push.assert_called_once()
        _, kwargs = mock_dlq.push.call_args
        assert "reason" in kwargs


class TestRQOutboundQueue:
    _EMAIL_KWARGS = dict(
        to_email="rq@example.com",
        subject="RQ Test",
        html="<p>RQ</p>",
        text="RQ",
        tag="rq_tag",
    )

    def _make_rq_queue(self) -> tuple[RQOutboundQueue, MagicMock]:
        mock_redis_lib = MagicMock()
        mock_rq = MagicMock()
        mock_conn = MagicMock()
        mock_rq_queue = MagicMock()
        mock_redis_lib.Redis.from_url.return_value = mock_conn
        mock_rq.Queue.return_value = mock_rq_queue
        with (
            patch.dict("sys.modules", {"redis": mock_redis_lib, "rq": mock_rq}),
        ):
            queue = RQOutboundQueue("redis://localhost:6379")
        queue._queue = mock_rq_queue
        return queue, mock_rq_queue

    def test_enqueue_returns_job_id_on_success(self):
        queue, mock_rq_queue = self._make_rq_queue()
        mock_job = MagicMock()
        mock_job.id = "job-abc-123"
        mock_rq_queue.enqueue.return_value = mock_job
        result = queue.enqueue_send_email(**self._EMAIL_KWARGS)
        assert result == "job-abc-123"

    def test_enqueue_falls_back_to_sync_on_exception(self, app):
        queue, mock_rq_queue = self._make_rq_queue()
        mock_rq_queue.enqueue.side_effect = Exception("Redis enqueue failed")

        mock_provider = MagicMock()
        with app.app_context():
            with patch(
                "app.services.email_provider.get_default_email_provider",
                return_value=mock_provider,
            ):
                result = queue.enqueue_send_email(**self._EMAIL_KWARGS)

        assert result is None
        mock_provider.send.assert_called_once()
