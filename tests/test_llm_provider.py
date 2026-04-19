"""Unit tests for app/services/llm_provider.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services.llm_provider import (
    ClaudeLLMProvider,
    LLMProvider,
    LLMProviderError,
    OpenAILLMProvider,
    StubLLMProvider,
    get_llm_provider,
)


class TestStubLLMProvider:
    def test_generate_returns_string(self):
        provider = StubLLMProvider()
        result = provider.generate("any prompt")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_satisfies_protocol(self):
        assert isinstance(StubLLMProvider(), LLMProvider)


class TestOpenAILLMProvider:
    def test_satisfies_protocol(self):
        assert isinstance(OpenAILLMProvider(), LLMProvider)

    def test_raises_when_api_key_missing(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        provider = OpenAILLMProvider()
        provider._api_key = ""
        with pytest.raises(LLMProviderError, match="OPENAI_API_KEY"):
            provider.generate("test prompt")

    def test_generate_returns_content_on_success(self, monkeypatch):
        provider = OpenAILLMProvider()
        provider._api_key = "test-key"

        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "AI insight here"}}]
        }
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            result = provider.generate("analyze my finances")

        assert result == "AI insight here"

    def test_generate_raises_on_request_failure(self):
        provider = OpenAILLMProvider()
        provider._api_key = "test-key"

        with patch("requests.post", side_effect=Exception("network error")):
            with pytest.raises(LLMProviderError, match="OpenAI call failed"):
                provider.generate("prompt")

    def test_uses_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_ADVISORY_MODEL", "gpt-4o")
        provider = OpenAILLMProvider()
        assert provider._model == "gpt-4o"

    def test_default_model_is_gpt4o_mini(self, monkeypatch):
        monkeypatch.delenv("OPENAI_ADVISORY_MODEL", raising=False)
        provider = OpenAILLMProvider()
        assert provider._model == "gpt-4o-mini"


class TestClaudeLLMProvider:
    def test_satisfies_protocol(self):
        assert isinstance(ClaudeLLMProvider(), LLMProvider)

    def test_raises_when_api_key_missing(self):
        provider = ClaudeLLMProvider()
        provider._api_key = ""
        with pytest.raises(LLMProviderError, match="ANTHROPIC_API_KEY"):
            provider.generate("test prompt")

    def test_generate_returns_content_on_success(self):
        provider = ClaudeLLMProvider()
        provider._api_key = "test-key"

        mock_resp = MagicMock()
        mock_resp.json.return_value = {"content": [{"text": "Claude insight"}]}
        mock_resp.raise_for_status.return_value = None

        with patch("requests.post", return_value=mock_resp):
            result = provider.generate("analyze my portfolio")

        assert result == "Claude insight"

    def test_generate_raises_on_request_failure(self):
        provider = ClaudeLLMProvider()
        provider._api_key = "test-key"

        with patch("requests.post", side_effect=Exception("timeout")):
            with pytest.raises(LLMProviderError, match="Claude call failed"):
                provider.generate("prompt")

    def test_uses_custom_model_from_env(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_ADVISORY_MODEL", "claude-opus-4-7")
        provider = ClaudeLLMProvider()
        assert provider._model == "claude-opus-4-7"


class TestGetLLMProvider:
    def test_returns_stub_by_default(self, monkeypatch):
        monkeypatch.delenv("LLM_PROVIDER", raising=False)
        provider = get_llm_provider()
        assert isinstance(provider, StubLLMProvider)

    def test_returns_stub_when_explicitly_set(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "stub")
        provider = get_llm_provider()
        assert isinstance(provider, StubLLMProvider)

    def test_returns_openai_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "openai")
        provider = get_llm_provider()
        assert isinstance(provider, OpenAILLMProvider)

    def test_returns_claude_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "claude")
        provider = get_llm_provider()
        assert isinstance(provider, ClaudeLLMProvider)

    def test_unknown_provider_falls_back_to_stub(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "unknown-provider")
        provider = get_llm_provider()
        assert isinstance(provider, StubLLMProvider)
