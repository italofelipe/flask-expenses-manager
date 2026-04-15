"""Tests for GET /advisory/insights (issue #1026).

Covers:
- Unauthenticated returns 401
- Authenticated user gets insights
- Response shape: insights list, generated_at, source, calls_remaining_today
- Stub provider returns insights without external calls
- LLM error triggers fallback (stub)
- Rate limit: 5 calls/day per user (mocked cache)
- Cache hit returns source=cache
- _parse_insights handles JSON, fallback text
"""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from app.application.services.advisory_service import (
    AdvisoryRateLimitError,
    AdvisoryService,
    _parse_insights,
)
from app.services.llm_provider import LLMProviderError, StubLLMProvider

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_and_login(client, prefix: str) -> str:
    suffix = uuid.uuid4().hex[:8]
    email = f"{prefix}-{suffix}@email.com"
    password = "StrongPass@123"
    reg = client.post(
        "/auth/register",
        json={"name": f"{prefix}-{suffix}", "email": email, "password": password},
    )
    assert reg.status_code == 201
    login = client.post("/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return login.get_json()["token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------


class TestAdvisoryAuthGate:
    def test_unauthenticated_returns_401(self, client) -> None:
        resp = client.get("/advisory/insights")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestAdvisoryInsights:
    def test_authenticated_user_gets_200(self, app, client) -> None:
        token = _register_and_login(client, prefix="adv-ok")
        resp = client.get("/advisory/insights", headers=_auth(token))
        assert resp.status_code == 200

    def test_response_has_required_keys(self, app, client) -> None:
        token = _register_and_login(client, prefix="adv-keys")
        resp = client.get("/advisory/insights", headers=_auth(token))
        assert resp.status_code == 200
        body = resp.get_json()
        data = body.get("data") or body
        required = {"insights", "generated_at", "source", "calls_remaining_today"}
        assert required.issubset(data.keys())

    def test_insights_is_list(self, app, client) -> None:
        token = _register_and_login(client, prefix="adv-list")
        resp = client.get("/advisory/insights", headers=_auth(token))
        data = resp.get_json().get("data") or resp.get_json()
        assert isinstance(data["insights"], list)
        assert len(data["insights"]) >= 1

    def test_each_insight_has_type_title_message(self, app, client) -> None:
        token = _register_and_login(client, prefix="adv-shape")
        resp = client.get("/advisory/insights", headers=_auth(token))
        data = resp.get_json().get("data") or resp.get_json()
        for insight in data["insights"]:
            assert "type" in insight
            assert "title" in insight
            assert "message" in insight

    def test_second_call_returns_cache(self, app) -> None:
        """With a real (mocked) cache, second call returns source=cache."""
        with app.app_context():
            user_id = uuid.uuid4()
            cached_result = {
                "insights": [{"type": "test", "title": "T", "message": "M"}],
                "generated_at": "2026-04-15",
                "source": "llm",
                "calls_remaining_today": 4,
            }
            cache_mock = MagicMock()
            # First call: insights cache miss, rate miss → generates
            # Second call: insights cache hit → returns cached
            cache_mock.get.side_effect = lambda key: (
                cached_result if "insights" in key else 0
            )

            service = AdvisoryService(user_id=user_id)
            service._cache = cache_mock

            result = service.get_insights()
            assert result["source"] == "cache"


# ---------------------------------------------------------------------------
# Rate limit
# ---------------------------------------------------------------------------


class TestAdvisoryRateLimit:
    def test_rate_limit_raises_after_5_calls(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()
            cache_mock = MagicMock()
            # Simulate 5 used calls; rate key → 5, insights key → None
            cache_mock.get.side_effect = lambda key: 5 if "rate" in key else None

            service = AdvisoryService(user_id=user_id)
            service._cache = cache_mock

            with pytest.raises(AdvisoryRateLimitError):
                service.get_insights()


# ---------------------------------------------------------------------------
# LLM provider fallback
# ---------------------------------------------------------------------------


class TestAdvisoryLLMFallback:
    def test_llm_error_falls_back_to_stub(self, app) -> None:
        with app.app_context():
            user_id = uuid.uuid4()

            broken_provider = MagicMock()
            broken_provider.generate.side_effect = LLMProviderError("API unavailable")

            cache_mock = MagicMock()
            cache_mock.get.return_value = None

            service = AdvisoryService(user_id=user_id, provider=broken_provider)
            service._cache = cache_mock

            result = service.get_insights()
            assert result["source"] == "stub"
            assert len(result["insights"]) >= 1


# ---------------------------------------------------------------------------
# Provider unit tests
# ---------------------------------------------------------------------------


class TestStubLLMProvider:
    def test_generates_non_empty_string(self) -> None:
        provider = StubLLMProvider()
        output = provider.generate("any prompt")
        assert isinstance(output, str)
        assert len(output) > 10


# ---------------------------------------------------------------------------
# _parse_insights unit tests
# ---------------------------------------------------------------------------


class TestParseInsights:
    def test_parses_valid_json_array(self) -> None:
        raw = '[{"type": "gasto_elevado", "title": "Altos", "message": "Reduza"}]'
        insights = _parse_insights(raw)
        assert len(insights) == 1
        assert insights[0]["type"] == "gasto_elevado"
        assert insights[0]["title"] == "Altos"

    def test_fallback_on_invalid_json(self) -> None:
        raw = "Aqui estão seus insights financeiros..."
        insights = _parse_insights(raw)
        assert len(insights) == 1
        assert insights[0]["type"] == "insight"
        assert "Aqui" in insights[0]["message"]

    def test_json_embedded_in_text(self) -> None:
        raw = (
            "Análise completa:\n\n"
            '[{"type": "meta_em_risco", "title": "Meta", "message": "Aporte"}]\n\n'
            "Espero que ajude!"
        )
        insights = _parse_insights(raw)
        assert insights[0]["type"] == "meta_em_risco"
