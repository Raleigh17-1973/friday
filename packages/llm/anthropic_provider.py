from __future__ import annotations

import os
from typing import Iterator

from packages.llm.base import LLMProvider


class AnthropicProvider(LLMProvider):
    def __init__(self) -> None:
        import anthropic  # type: ignore[import]

        self._client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self._model = os.getenv("FRIDAY_LLM_MODEL", "claude-sonnet-4-6")

    def complete(self, system: str, prompt: str, **kwargs) -> str:
        max_tokens = int(kwargs.get("max_tokens", 2048))
        response = self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text

    def stream(self, system: str, prompt: str, **kwargs) -> Iterator[str]:
        max_tokens = int(kwargs.get("max_tokens", 2048))
        with self._client.messages.stream(
            model=self._model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            yield from stream.text_stream
