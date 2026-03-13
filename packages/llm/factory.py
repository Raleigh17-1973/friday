from __future__ import annotations

import logging
import os

from packages.llm.base import LLMProvider

_log = logging.getLogger(__name__)


def create_llm_provider() -> LLMProvider | None:
    """
    Create an LLM provider based on env vars.

    FRIDAY_LLM_PROVIDER: 'anthropic' (default) | 'openai'
    ANTHROPIC_API_KEY / OPENAI_API_KEY: required for respective providers.

    Returns None if the provider SDK is not installed or the API key is missing,
    allowing the system to fall back to stub responses gracefully.
    """
    provider_name = os.getenv("FRIDAY_LLM_PROVIDER", "anthropic").strip().lower()

    if provider_name == "anthropic":
        if not os.getenv("ANTHROPIC_API_KEY"):
            _log.warning("ANTHROPIC_API_KEY not set — LLM disabled, using stubs")
            return None
        try:
            from packages.llm.anthropic_provider import AnthropicProvider
            provider = AnthropicProvider()
            _log.info("Anthropic LLM provider initialised (model=%s)", os.getenv("FRIDAY_LLM_MODEL", "claude-sonnet-4-6"))
            return provider
        except Exception as exc:
            _log.warning("Anthropic provider failed to init: %s — falling back to stubs", exc)
            return None

    if provider_name == "openai":
        if not os.getenv("OPENAI_API_KEY"):
            _log.warning("OPENAI_API_KEY not set — LLM disabled, using stubs")
            return None
        try:
            from packages.llm.openai_provider import OpenAIProvider
            provider = OpenAIProvider()
            _log.info("OpenAI LLM provider initialised (model=%s)", os.getenv("FRIDAY_LLM_MODEL", "gpt-4o"))
            return provider
        except Exception as exc:
            _log.warning("OpenAI provider failed to init: %s — falling back to stubs", exc)
            return None

    _log.warning("Unknown FRIDAY_LLM_PROVIDER=%r — LLM disabled", provider_name)
    return None
