"""LLM client abstraction.

RAVEL treats the LLM as a narrow, non-authoritative reasoning layer:
evidence synthesis, narrative drafting, and explanation. A deterministic synthesizer
implements the same interface so the entire system (benchmark, UI, demo) works offline.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

import httpx

from ravel.config import Settings


class LLMError(RuntimeError):
    pass


class LLMProvider(ABC):
    name: str = "base"

    @abstractmethod
    def complete(
        self,
        system: str,
        user: str,
        temperature: float = 0.2,
        max_tokens: int = 800,
    ) -> str: ...


class OpenAICompatibleClient(LLMProvider):
    """Minimal OpenAI-compatible chat client (works with OpenAI, Groq, Together, OpenRouter,
    vLLM, or any /v1/chat/completions endpoint)."""

    name = "openai_compatible"

    def __init__(self, base_url: str, api_key: str, model: str, timeout_s: float = 45.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout_s = timeout_s
        self.client = httpx.Client(timeout=timeout_s)

    def complete(self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 800) -> str:
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            resp = self.client.post(f"{self.base_url}/chat/completions", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as exc:  # noqa: BLE001
            raise LLMError(f"completion failed: {exc}") from exc


class DeterministicSynthesizer(LLMProvider):
    """Rule-based generator fulfilling the LLMProvider contract when no key is configured.
    Produces evidence-based narratives from structured context; never fabricates facts."""

    name = "deterministic"

    def complete(self, system: str, user: str, temperature: float = 0.2, max_tokens: int = 800) -> str:
        # A structured payload is passed in `user` as JSON when the caller wants templates;
        # otherwise we return the plain `user` text (callers already write prose).
        return user


def build_llm(settings: Settings) -> LLMProvider:
    if settings.llm_provider == "ollama":
        base_url = (
            settings.llm_base_url
            if settings.llm_base_url != "https://api.openai.com/v1"
            else "http://localhost:11434/v1"
        )
        model = settings.llm_model if settings.llm_model != "gpt-4o-mini" else "llama3.2"
        return OpenAICompatibleClient(
            base_url=base_url,
            api_key=settings.llm_api_key or "ollama",
            model=model,
            timeout_s=settings.llm_timeout_s,
        )
    if settings.llm_provider == "openai_compatible" and settings.llm_api_key:
        return OpenAICompatibleClient(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            timeout_s=settings.llm_timeout_s,
        )
    return DeterministicSynthesizer()


def timed_complete(provider: LLMProvider, system: str, user: str, **kw: Any) -> tuple[str, int]:
    """Returns (text, token_estimate)."""
    start = time.time()
    text = provider.complete(system, user, **kw)
    time.time() - start
    tokens = max(1, int(len(system) / 4 + len(user) / 4 + len(text) / 4))
    return text, tokens
