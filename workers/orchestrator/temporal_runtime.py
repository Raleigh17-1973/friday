from __future__ import annotations

from typing import Any, Callable

_RUN_HANDLER: Callable[[dict[str, Any]], dict[str, Any]] | None = None


def configure_run_handler(handler: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    global _RUN_HANDLER
    _RUN_HANDLER = handler


def run_handler(payload: dict[str, Any]) -> dict[str, Any]:
    if _RUN_HANDLER is None:
        raise RuntimeError("Temporal run handler is not configured")
    return _RUN_HANDLER(payload)
