from __future__ import annotations

import json
import os
from typing import Iterator

from packages.llm.base import LLMProvider, _parse_llm_json


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

    def stream(self, system: str, prompt: str, **kwargs) -> Iterator[str]:
        max_tokens = int(kwargs.get("max_tokens", 2048))
        for chunk in self._client.chat.completions.create(
            model=self._model,
            max_tokens=max_tokens,
            stream=True,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
        ):
            delta = chunk.choices[0].delta.content
            if delta:
                yield delta

    def complete_structured(self, system: str, prompt: str, schema: dict, **kwargs) -> dict:
        """Use OpenAI's native JSON schema response_format (strict=True) for guaranteed structure."""
        model = kwargs.get("model", os.getenv("FRIDAY_PROCESS_MODEL", self._model))
        try:
            response = self._client.chat.completions.create(
                model=model,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "StructuredOutput",
                        "strict": True,
                        "schema": schema,
                    },
                },
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
            )
            content = response.choices[0].message.content or ""
            return json.loads(content)
        except Exception:
            # Graceful fallback to prompt-based JSON if structured outputs fail
            # (e.g. model doesn't support response_format, or schema has unsupported types)
            return self.complete_json(system, prompt, **kwargs)
