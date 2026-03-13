from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from typing import Iterator


class LLMProvider(ABC):
    """Abstract base for pluggable LLM providers."""

    @abstractmethod
    def complete(self, system: str, prompt: str, **kwargs) -> str:
        """Send a system + user prompt and return the full text response."""

    def stream(self, system: str, prompt: str, **kwargs) -> Iterator[str]:
        """
        Send a system + user prompt and yield response tokens as they arrive.
        Default: runs complete() and yields the whole string as one chunk.
        Providers should override for true streaming.
        """
        yield self.complete(system, prompt, **kwargs)

    def complete_json(self, system: str, prompt: str, **kwargs) -> dict:
        """Send a prompt expecting JSON back. Returns parsed dict or empty dict on failure."""
        text = self.complete(system, prompt, **kwargs)
        return _parse_llm_json(text)

    def complete_structured(self, system: str, prompt: str, schema: dict, **kwargs) -> dict:
        """
        Send a prompt with a JSON schema response_format for guaranteed structure.
        Default: falls back to complete_json() (prompt-based). Providers that support
        native structured outputs (e.g. OpenAI) should override for schema enforcement.
        """
        return self.complete_json(system, prompt, **kwargs)


def _parse_llm_json(text: str) -> dict:
    """Strip markdown fences and parse JSON from LLM output."""
    text = text.strip()
    # Strip ```json ... ``` or ``` ... ``` fences
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        result = json.loads(text)
        if isinstance(result, dict):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    # Try extracting the first { ... } block
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass
    return {}
