"""LLM provider abstraction for the AI advisory engine.

Provider pattern: configure via LLM_PROVIDER env var.
  - "stub"   (default) — rule-based insights, no external calls
  - "openai" — OpenAI chat completions (requires OPENAI_API_KEY)
  - "claude" — Anthropic Messages API (requires ANTHROPIC_API_KEY)
"""

from __future__ import annotations

import os
from typing import Protocol, runtime_checkable


class LLMProviderError(Exception):
    """Raised when the LLM provider fails."""


@runtime_checkable
class LLMProvider(Protocol):
    def generate(self, prompt: str) -> str:
        """Generate a response for *prompt*. Raises LLMProviderError on failure."""
        ...


class StubLLMProvider:
    """Canned response — useful for testing and environments without API keys."""

    def generate(self, prompt: str) -> str:  # noqa: ARG002
        return (  # noqa: E501
            "Com base nos seus dados financeiros, identifiquei os seguintes insights: "
            "1. Gastos discricionários >30% das despesas — revise esses valores. "  # noqa: E501
            "2. Você tem metas ativas que podem estar em risco caso o ritmo de gastos atual continue. "  # noqa: E501
            "3. Há uma oportunidade de economia de até 15% caso reduza gastos variáveis nos próximos 60 dias."  # noqa: E501
        )


class OpenAILLMProvider:
    """Calls the OpenAI Chat Completions API (requires `requests` + OPENAI_API_KEY)."""

    _BASE_URL = "https://api.openai.com/v1/chat/completions"

    def __init__(self) -> None:
        self._api_key = os.getenv("OPENAI_API_KEY", "")
        self._model = os.getenv("OPENAI_ADVISORY_MODEL", "gpt-4o-mini")

    def generate(self, prompt: str) -> str:
        if not self._api_key:
            raise LLMProviderError("OPENAI_API_KEY is not configured.")
        import requests  # lazy import to keep startup fast

        try:
            resp = requests.post(
                self._BASE_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                    "temperature": 0.4,
                },
                timeout=20,
            )
            resp.raise_for_status()
            return str(resp.json()["choices"][0]["message"]["content"])
        except Exception as exc:
            raise LLMProviderError(f"OpenAI call failed: {exc}") from exc


class ClaudeLLMProvider:
    """Calls the Anthropic Messages API (requires `requests` + ANTHROPIC_API_KEY)."""

    _BASE_URL = "https://api.anthropic.com/v1/messages"

    def __init__(self) -> None:
        self._api_key = os.getenv("ANTHROPIC_API_KEY", "")
        self._model = os.getenv("ANTHROPIC_ADVISORY_MODEL", "claude-haiku-4-5-20251001")

    def generate(self, prompt: str) -> str:
        if not self._api_key:
            raise LLMProviderError("ANTHROPIC_API_KEY is not configured.")
        import requests

        try:
            resp = requests.post(
                self._BASE_URL,
                headers={
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "max_tokens": 512,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=20,
            )
            resp.raise_for_status()
            return str(resp.json()["content"][0]["text"])
        except Exception as exc:
            raise LLMProviderError(f"Claude call failed: {exc}") from exc


def get_llm_provider() -> LLMProvider:
    """Factory: reads LLM_PROVIDER env var and returns the appropriate provider."""
    provider_name = os.getenv("LLM_PROVIDER", "stub").lower()
    if provider_name == "openai":
        return OpenAILLMProvider()
    if provider_name == "claude":
        return ClaudeLLMProvider()
    return StubLLMProvider()


__all__ = [
    "ClaudeLLMProvider",
    "LLMProvider",
    "LLMProviderError",
    "OpenAILLMProvider",
    "StubLLMProvider",
    "get_llm_provider",
]
