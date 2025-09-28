"""Unified LLM routing with adaptive rate limiting and provider failover."""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

import requests

from utils.rate_limiter import groq_rate_limiter


class ProviderRateLimitError(RuntimeError):
    """Raised when a provider reports a rate limit condition."""


class ProviderError(RuntimeError):
    """Raised for generic provider failures."""


def _extract_json(content: str) -> Dict[str, Any]:
    """Best-effort JSON extraction from LLM responses."""
    if not content:
        return {"error": "Empty response from model"}

    content = content.strip()
    # Direct parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Remove fenced code blocks if present
    fenced_patterns = [
        r"```json\s*(\{.*?\})\s*```",
        r"```\s*(\{.*?\})\s*```",
        r"(\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})",
    ]

    for pattern in fenced_patterns:
        matches = re.findall(pattern, content, flags=re.DOTALL | re.MULTILINE)
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue

    # Fallback: return the content wrapped in a response object
    return {"response": content, "error": "Could not parse as JSON"}


@dataclass
class ProviderConfig:
    name: str
    priority: int


class BaseProvider:
    """Base class for LLM providers."""

    def __init__(self, name: str, priority: int = 10) -> None:
        self.config = ProviderConfig(name=name, priority=priority)

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.2,
        max_tokens: int = 900,
        timeout: int = 60,
    ) -> Any:
        raise NotImplementedError


class GroqProvider(BaseProvider):
    """Groq provider using the OpenAI-compatible chat completions API."""

    def __init__(self, api_key: str, model: str = "llama-3.1-8b-instant") -> None:
        super().__init__(name="groq", priority=0)
        self.api_key = api_key
        self.model = model
        self.base_url = os.getenv("GROQ_API_BASE", "https://api.groq.com/openai/v1")

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.2,
        max_tokens: int = 900,
        timeout: int = 60,
    ) -> Any:
        groq_rate_limiter.wait_if_needed()

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": [],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if system:
            payload["messages"].append({"role": "system", "content": system})
        payload["messages"].append({"role": "user", "content": prompt})

        if response_format == "json":
            payload["response_format"] = {"type": "json_object"}

        response = requests.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
            timeout=timeout,
        )

        if response.status_code == 429:
            raise ProviderRateLimitError("Groq rate limit reached")
        if response.status_code >= 500:
            raise ProviderRateLimitError("Groq temporary server error")
        if response.status_code >= 400:
            raise ProviderError(
                f"Groq request failed ({response.status_code}): {response.text[:200]}"
            )

        data = response.json()
        message = data["choices"][0]["message"]["content"]
        if response_format == "json":
            return _extract_json(message)
        return message


class LLMRouter:
    """High-level router that fans out requests across providers."""

    def __init__(self, providers: Optional[Iterable[BaseProvider]] = None) -> None:
        if providers is not None:
            provider_list = list(providers)
        else:
            provider_list = self._discover_providers()

        if not provider_list:
            raise RuntimeError(
                "No LLM provider configured. Set GROQ_API_KEY in your environment variables."
            )

        # sort by provider priority to make sure primary executes first
        self.providers: List[BaseProvider] = sorted(
            provider_list, key=lambda p: p.config.priority
        )

    @staticmethod
    def _discover_providers() -> List[BaseProvider]:
        providers: List[BaseProvider] = []

        groq_api_key = os.getenv("GROQ_API_KEY")
        if groq_api_key:
            groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
            providers.append(GroqProvider(api_key=groq_api_key, model=groq_model))

        return providers

    def complete(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        response_format: str = "json",
        temperature: float = 0.2,
        max_tokens: int = 900,
        timeout: int = 60,
        retry_delay: float = 2.0,
    ) -> Any:
        """Execute the prompt against the first healthy provider."""
        last_error: Optional[str] = None

        for provider in self.providers:
            start = time.time()
            try:
                result = provider.complete(
                    prompt,
                    system=system,
                    response_format=response_format,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    timeout=timeout,
                )
                latency = time.time() - start
                print(
                    f"🤖 Provider '{provider.config.name}' served request in {latency:.2f}s"
                )
                return result
            except ProviderRateLimitError as exc:
                last_error = f"{provider.config.name}: {exc}"
                print(f"⚠️ {last_error}. Trying next provider...")
                time.sleep(retry_delay)
            except ProviderError as exc:
                last_error = f"{provider.config.name}: {exc}"
                print(f"⚠️ {last_error}. Trying next provider...")
            except Exception as exc:  # noqa: BLE001
                last_error = f"{provider.config.name}: {exc}"
                print(f"⚠️ Unexpected provider failure: {last_error}")

        raise RuntimeError(last_error or "All LLM providers failed")
