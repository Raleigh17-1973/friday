"""Structured observability for Friday LLM calls.

Logs every LLM invocation as a JSON record and tracks cumulative cost per run.
Uses Python's standard logging infrastructure — no external dependencies required.

Usage
-----
    from packages.observability.logger import LLMCallLogger

    logger = LLMCallLogger()
    with logger.trace(run_id="run_abc123", specialist="finance", model="gpt-4o") as ctx:
        result = llm.complete(system, prompt)
        ctx.finish(
            input_tokens=estimate_tokens(system + prompt),
            output_tokens=estimate_tokens(result),
        )

Or as a simple one-shot log:

    logger.record(
        run_id="run_abc123",
        specialist="synthesizer",
        model="gpt-4o",
        input_tokens=800,
        output_tokens=350,
        latency_ms=2140,
        success=True,
    )
"""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Generator

_log = logging.getLogger("friday.observability")

# ---------------------------------------------------------------------------
# Token-cost tables (USD per 1 000 tokens, as of early 2025)
# Update these when pricing changes.
# ---------------------------------------------------------------------------
_COST_TABLE: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o":               {"input": 0.005,   "output": 0.015},
    "gpt-4o-mini":          {"input": 0.00015,  "output": 0.0006},
    "gpt-4-turbo":          {"input": 0.01,    "output": 0.03},
    "gpt-3.5-turbo":        {"input": 0.0005,  "output": 0.0015},
    # Anthropic
    "claude-opus-4-5":      {"input": 0.015,   "output": 0.075},
    "claude-sonnet-4-6":    {"input": 0.003,   "output": 0.015},
    "claude-haiku-3":       {"input": 0.00025, "output": 0.00125},
}

# Warn if a single run exceeds this amount
_SINGLE_RUN_COST_WARN_USD = 0.50


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Return estimated cost in USD. Returns 0.0 if model not in table."""
    prices = _COST_TABLE.get(model, {})
    if not prices:
        return 0.0
    cost = (input_tokens / 1000) * prices["input"] + (output_tokens / 1000) * prices["output"]
    return round(cost, 6)


# ---------------------------------------------------------------------------
# Run-level cost accumulator
# ---------------------------------------------------------------------------

@dataclass
class RunCostAccumulator:
    """Accumulate cost across multiple LLM calls within a single run."""
    run_id: str
    total_cost_usd: float = 0.0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    call_count: int = 0
    specialists: list[str] = field(default_factory=list)

    def add(self, specialist: str, cost_usd: float, input_tokens: int, output_tokens: int) -> None:
        self.total_cost_usd += cost_usd
        self.total_input_tokens += input_tokens
        self.total_output_tokens += output_tokens
        self.call_count += 1
        if specialist not in self.specialists:
            self.specialists.append(specialist)

    def summarize(self) -> dict:
        return {
            "run_id": self.run_id,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "llm_calls": self.call_count,
            "specialists": self.specialists,
        }


# ---------------------------------------------------------------------------
# Main logger class
# ---------------------------------------------------------------------------

class LLMCallLogger:
    """Thread-safe structured logger for LLM calls."""

    def __init__(self) -> None:
        self._accumulators: dict[str, RunCostAccumulator] = {}

    def _get_accumulator(self, run_id: str) -> RunCostAccumulator:
        if run_id not in self._accumulators:
            self._accumulators[run_id] = RunCostAccumulator(run_id=run_id)
        return self._accumulators[run_id]

    def record(
        self,
        *,
        run_id: str,
        specialist: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
        success: bool,
        error: str | None = None,
    ) -> dict:
        """Log a single LLM call and return the log record dict."""
        cost_usd = _estimate_cost(model, input_tokens, output_tokens)
        record = {
            "run_id": run_id,
            "specialist": specialist,
            "model": model,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "latency_ms": round(latency_ms, 1),
            "cost_usd": cost_usd,
            "success": success,
        }
        if error:
            record["error"] = error

        if success:
            _log.info("llm_call %s", json.dumps(record))
        else:
            _log.warning("llm_call_failed %s", json.dumps(record))

        acc = self._get_accumulator(run_id)
        acc.add(specialist, cost_usd, input_tokens, output_tokens)

        if acc.total_cost_usd > _SINGLE_RUN_COST_WARN_USD:
            _log.warning(
                "run_cost_high run_id=%s total_usd=%.4f calls=%d",
                run_id,
                acc.total_cost_usd,
                acc.call_count,
            )

        return record

    def finalize_run(self, run_id: str) -> dict:
        """Return and remove the cost summary for a completed run."""
        acc = self._accumulators.pop(run_id, None)
        if acc is None:
            return {"run_id": run_id, "total_cost_usd": 0.0, "llm_calls": 0}
        summary = acc.summarize()
        _log.info("run_complete %s", json.dumps(summary))
        return summary

    @contextmanager
    def trace(
        self,
        *,
        run_id: str,
        specialist: str,
        model: str,
    ) -> Generator["_TraceContext", None, None]:
        """Context manager that measures wall-clock latency automatically.

        Example::

            with logger.trace(run_id=run_id, specialist="finance", model="gpt-4o") as ctx:
                text = llm.complete(system, prompt)
                ctx.finish(input_tokens=800, output_tokens=len(text.split()))
        """
        ctx = _TraceContext(logger=self, run_id=run_id, specialist=specialist, model=model)
        ctx._start = time.monotonic()
        try:
            yield ctx
        except Exception as exc:
            if not ctx._finished:
                ctx.finish(input_tokens=0, output_tokens=0, success=False, error=str(exc))
            raise


class _TraceContext:
    """Internal context object yielded by LLMCallLogger.trace()."""

    def __init__(self, *, logger: LLMCallLogger, run_id: str, specialist: str, model: str) -> None:
        self._logger = logger
        self._run_id = run_id
        self._specialist = specialist
        self._model = model
        self._start: float = time.monotonic()
        self._finished = False

    def finish(
        self,
        *,
        input_tokens: int,
        output_tokens: int,
        success: bool = True,
        error: str | None = None,
    ) -> dict:
        latency_ms = (time.monotonic() - self._start) * 1000
        self._finished = True
        return self._logger.record(
            run_id=self._run_id,
            specialist=self._specialist,
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            success=success,
            error=error,
        )


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

_default_logger = LLMCallLogger()


def record_llm_call(
    *,
    run_id: str,
    specialist: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    latency_ms: float,
    success: bool = True,
    error: str | None = None,
) -> dict:
    """Convenience wrapper around the module-level logger."""
    return _default_logger.record(
        run_id=run_id,
        specialist=specialist,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=latency_ms,
        success=success,
        error=error,
    )


def finalize_run(run_id: str) -> dict:
    """Return cost summary and clear accumulator for a completed run."""
    return _default_logger.finalize_run(run_id)
