"""PERF-GAP-04 — Tests for retry_wrapper and its integration with Resend,
Asaas, and BRAPI.

Uses unittest.mock to simulate transient HTTP failures (Timeout, HTTPError,
ConnectionError) and verify that tenacity retries and ultimately raises on
exhaustion, and that success on a later attempt is returned correctly.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests
from requests.exceptions import ConnectionError, HTTPError, Timeout
from tenacity import wait_exponential_jitter

from app.services.retry_wrapper import (
    _JITTER_MAX,
    _WAIT_INITIAL,
    _WAIT_MAX,
    _make_before_sleep,
    with_retry,
)

# ---------------------------------------------------------------------------
# retry_wrapper unit tests
# ---------------------------------------------------------------------------


class TestWithRetry:
    def test_success_on_first_attempt(self) -> None:
        call_count = 0

        @with_retry(provider="test")
        def _fn() -> str:
            nonlocal call_count
            call_count += 1
            return "ok"

        assert _fn() == "ok"
        assert call_count == 1

    def test_retries_on_timeout_then_succeeds(self) -> None:
        call_count = 0

        @with_retry(provider="test")
        def _fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Timeout("transient timeout")
            return "ok"

        with patch("tenacity.nap.time"):  # skip actual sleep in tests
            result = _fn()

        assert result == "ok"
        assert call_count == 2

    def test_retries_on_http_error_then_succeeds(self) -> None:
        call_count = 0
        mock_resp = MagicMock()
        mock_resp.status_code = 503

        @with_retry(provider="test")
        def _fn() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise HTTPError("boom", response=mock_resp)
            return "recovered"

        with patch("tenacity.nap.time"):
            result = _fn()

        assert result == "recovered"
        assert call_count == 3

    def test_raises_after_max_attempts_exhausted(self) -> None:
        call_count = 0

        @with_retry(provider="test")
        def _fn() -> None:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("network down")

        with patch("tenacity.nap.time"), pytest.raises(ConnectionError):
            _fn()

        assert call_count == 3  # _MAX_ATTEMPTS = 3

    def test_non_retryable_exception_not_retried(self) -> None:
        call_count = 0

        @with_retry(provider="test")
        def _fn() -> None:
            nonlocal call_count
            call_count += 1
            raise ValueError("logic error — not retryable")

        with pytest.raises(ValueError):
            _fn()

        assert call_count == 1  # no retry for non-transient errors

    def test_jitter_produces_varying_wait_times(self) -> None:
        """Verify that wait_exponential_jitter produces non-identical waits."""
        strategy = wait_exponential_jitter(
            initial=_WAIT_INITIAL, max=_WAIT_MAX, jitter=_JITTER_MAX
        )
        mock_state = MagicMock()
        mock_state.attempt_number = 1
        # Sample wait times — with jitter they should vary
        waits = {strategy(retry_state=mock_state) for _ in range(20)}
        # With jitter > 0, we expect more than 1 distinct wait value
        assert len(waits) > 1, "Jitter should produce varying wait times"

    def test_before_sleep_logs_elapsed_and_outcome(self) -> None:
        callback = _make_before_sleep("test-provider")
        mock_state = MagicMock()
        mock_state.attempt_number = 2
        mock_state.seconds_since_start = 3.45
        mock_state.outcome.exception.return_value = Timeout("transient")
        mock_state.next_action = MagicMock()
        mock_state.next_action.sleep = 4.0

        with patch("app.services.retry_wrapper._logger") as mock_logger:
            callback(mock_state)

        call_args = mock_logger.warning.call_args
        log_msg = call_args[0][0]
        assert "elapsed=" in log_msg
        assert "outcome=" in log_msg


# ---------------------------------------------------------------------------
# ResendEmailProvider retry integration
# ---------------------------------------------------------------------------


class TestResendEmailProviderRetry:
    def test_send_retries_on_connection_error_then_succeeds(self, app) -> None:
        from app.services.email_provider import EmailMessage, ResendEmailProvider

        call_count = 0
        ok_response = MagicMock()
        ok_response.ok = True
        ok_response.json.return_value = {"id": "msg-abc"}

        def _mock_post(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("transient")
            return ok_response

        with app.app_context():
            provider = ResendEmailProvider()
            provider._api_key = "test-key"
            provider._from_email = "from@test.com"

            with (
                patch.object(provider._session, "post", side_effect=_mock_post),
                patch("tenacity.nap.time"),
            ):
                result = provider.send(
                    EmailMessage(
                        to_email="u@example.com",
                        subject="Test",
                        html="<p>Hi</p>",
                        text="Hi",
                        tag="test",
                    )
                )

        assert result.provider == "resend"
        assert result.provider_message_id == "msg-abc"
        assert call_count == 2

    def test_send_raises_after_all_retries_exhausted(self, app) -> None:
        from app.services.email_provider import (
            EmailMessage,
            EmailProviderError,
            ResendEmailProvider,
        )

        with app.app_context():
            provider = ResendEmailProvider()
            provider._api_key = "test-key"
            provider._from_email = "from@test.com"

            with (
                patch.object(
                    provider._session,
                    "post",
                    side_effect=Timeout("always timeout"),
                ),
                patch("tenacity.nap.time"),
                pytest.raises(EmailProviderError),
            ):
                provider.send(
                    EmailMessage(
                        to_email="u@example.com",
                        subject="Test",
                        html="<p>Hi</p>",
                        text="Hi",
                        tag="test",
                    )
                )


# ---------------------------------------------------------------------------
# AsaasBillingProvider retry integration
# ---------------------------------------------------------------------------


class TestAsaasBillingProviderRetry:
    def test_request_retries_on_timeout_then_succeeds(self, app) -> None:
        from app.services.billing_adapter import AsaasBillingProvider

        call_count = 0
        ok_response = MagicMock()
        ok_response.ok = True
        ok_response.json.return_value = {"id": "sub-1", "status": "active"}

        def _mock_request(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Timeout("transient")
            return ok_response

        with app.app_context():
            provider = AsaasBillingProvider()
            provider._api_key = "test-key"

            with (
                patch.object(provider._session, "request", side_effect=_mock_request),
                patch("tenacity.nap.time"),
            ):
                result = provider.get_subscription("sub-1")

        assert result["status"] == "active"
        assert call_count == 2

    def test_request_raises_after_all_retries_exhausted(self, app) -> None:
        from app.services.billing_adapter import (
            AsaasBillingProvider,
            BillingProviderError,
        )

        with app.app_context():
            provider = AsaasBillingProvider()
            provider._api_key = "test-key"

            with (
                patch.object(
                    provider._session,
                    "request",
                    side_effect=ConnectionError("always down"),
                ),
                patch("tenacity.nap.time"),
                pytest.raises(BillingProviderError),
            ):
                provider.get_subscription("sub-1")


# ---------------------------------------------------------------------------
# InvestmentService BRAPI retry integration
# ---------------------------------------------------------------------------


class TestBrapiRetryIntegration:
    def test_request_json_retries_on_http_error_then_succeeds(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.investment_service import InvestmentService

        InvestmentService._clear_cache_for_tests()
        call_count = 0

        ok_response = MagicMock()
        ok_response.raise_for_status.return_value = None
        ok_response.json.return_value = {"results": [{"regularMarketPrice": 10.5}]}

        error_response = MagicMock()
        error_response.raise_for_status.side_effect = HTTPError("503")

        def _fake_get(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            return error_response if call_count < 2 else ok_response

        monkeypatch.setattr(requests, "get", _fake_get)

        with patch("tenacity.nap.time"):
            price = InvestmentService.get_market_price("PETR4")

        assert price == 10.5
        assert call_count == 2

    def test_request_json_returns_none_after_all_retries_exhausted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from app.services.investment_service import InvestmentService

        InvestmentService._clear_cache_for_tests()
        call_count = 0

        def _always_timeout(*args, **kwargs):  # type: ignore[no-untyped-def]
            nonlocal call_count
            call_count += 1
            raise Timeout("always timeout")

        monkeypatch.setattr(requests, "get", _always_timeout)

        with patch("tenacity.nap.time"):
            price = InvestmentService.get_market_price("PETR4")

        # After all retries, investment_service catches and returns None
        assert price is None
        assert call_count == 3  # tenacity retried _MAX_ATTEMPTS=3 times
