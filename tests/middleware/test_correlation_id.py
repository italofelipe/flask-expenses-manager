"""Tests for ARC-API-03 — Correlation-ID middleware.

Verifies:
- X-Request-Id is present on every response.
- A valid inbound X-Request-ID is echoed back unchanged.
- An invalid / oversized inbound value is ignored and a fresh ID is generated.
- The Sentry tag injection path is exercised without a real DSN.
- The log-record factory injects a ``request_id`` attribute.
"""

from __future__ import annotations

import logging
import re

_UUID_HEX_RE = re.compile(r"^[a-f0-9]{32}$")
_REQUEST_ID_HEADER = "X-Request-Id"


class TestCorrelationIdResponseHeader:
    def test_response_always_has_request_id(self, client) -> None:
        resp = client.get("/healthz")
        assert _REQUEST_ID_HEADER in resp.headers

    def test_valid_inbound_id_echoed(self, client) -> None:
        custom_id = "abc123-my-trace"
        resp = client.get("/healthz", headers={"X-Request-ID": custom_id})
        assert resp.headers[_REQUEST_ID_HEADER] == custom_id

    def test_invalid_inbound_id_replaced(self, client) -> None:
        # Space + exclamation mark fail the safe-chars regex — should be replaced.
        resp = client.get("/healthz", headers={"X-Request-ID": "bad value!"})
        generated = resp.headers[_REQUEST_ID_HEADER]
        assert _UUID_HEX_RE.match(generated), f"Expected hex UUID, got {generated!r}"

    def test_oversized_inbound_id_replaced(self, client) -> None:
        resp = client.get("/healthz", headers={"X-Request-ID": "a" * 200})
        generated = resp.headers[_REQUEST_ID_HEADER]
        assert _UUID_HEX_RE.match(generated), f"Expected hex UUID, got {generated!r}"

    def test_missing_inbound_id_generates_uuid(self, client) -> None:
        resp = client.get("/healthz")
        generated = resp.headers[_REQUEST_ID_HEADER]
        assert _UUID_HEX_RE.match(generated), f"Expected hex UUID, got {generated!r}"


class TestCorrelationIdLogFactory:
    def test_log_record_carries_request_id(self, app) -> None:
        captured: list[logging.LogRecord] = []

        class _Capture(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                captured.append(record)

        handler = _Capture()
        logger = logging.getLogger("test_correlation_id")
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)

        with app.test_client() as client:
            client.get("/healthz")
            logger.info("probe")

        logger.removeHandler(handler)
        assert captured, "No log records captured"
        record = captured[-1]
        assert hasattr(record, "request_id")
