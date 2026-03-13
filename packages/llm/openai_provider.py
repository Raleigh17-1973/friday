from __future__ import annotations

import os

from packages.llm.base import LLMProvider


class OpenAIProvider(LLMProvider):
    def __init__(self) -> None:
        import openai  # type: ignore[import]

        self._client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self._model = os.getenv("FRIDAY_LLM_MODEL", "gpt-4o")

    def complete(self, system: str, prompt: str, **kwargs) -> str:
        max_tokens = int(kwargs.get("max_tokens", 2048))
        response = self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        )
        return response.choices[0].message.content or ""
