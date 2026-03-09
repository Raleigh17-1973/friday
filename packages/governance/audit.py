from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Any

from packages.common.models import RunTrace
from packages.governance.run_store import RunStore


class AuditLog:
    def __init__(self, *, run_store: RunStore | None = None) -> None:
        self._run_store = run_store
        self._runs: dict[str, RunTrace] = {}
        self._events: dict[str, list[dict[str, Any]]] = defaultdict(list)

    def record_run(self, trace: RunTrace) -> None:
        self._runs[trace.run_id] = trace
        event = {"type": "run_recorded", "trace": asdict(trace)}
        self._events[trace.run_id].append(event)
        if self._run_store is not None:
            self._run_store.save_run(trace.run_id, asdict(trace))
            self._run_store.append_event(trace.run_id, event)

    def append_event(self, run_id: str, event: dict[str, Any]) -> None:
        self._events[run_id].append(event)
        if self._run_store is not None:
            self._run_store.append_event(run_id, event)

    def get_run(self, run_id: str) -> RunTrace | None:
        in_memory = self._runs.get(run_id)
        if in_memory is not None:
            return in_memory

        if self._run_store is None:
            return None
        stored = self._run_store.get_run(run_id)
        if stored is None:
            return None
        trace = RunTrace.from_dict(stored)
        self._runs[run_id] = trace
        return trace

    def get_events(self, run_id: str) -> list[dict[str, Any]]:
        if run_id in self._events and self._events[run_id]:
            return list(self._events[run_id])
        if self._run_store is None:
            return list(self._events[run_id])
        events = self._run_store.get_events(run_id)
        self._events[run_id] = list(events)
        return events
