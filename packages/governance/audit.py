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

    def list_runs(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return lightweight run summaries (run_id, conversation_id, user_id, created_at)."""
        in_memory = [
            {
                "run_id": t.run_id,
                "conversation_id": t.conversation_id,
                "user_id": t.user_id,
                "created_at": t.created_at,
            }
            for t in sorted(self._runs.values(), key=lambda t: t.created_at, reverse=True)
        ]
        if in_memory:
            return in_memory[:limit]
        if self._run_store is not None:
            return self._run_store.list_runs(limit=limit)
        return []

    def get_latest_run_for_conversation(self, conversation_id: str) -> RunTrace | None:
        """Return the most recent RunTrace for a given conversation_id."""
        # Check in-memory store first (most recent session)
        candidates = [
            t for t in self._runs.values()
            if t.conversation_id == conversation_id
        ]
        if candidates:
            latest = max(candidates, key=lambda t: t.created_at)
            return latest
        # Fall back to run_store summary lookup
        if self._run_store is not None:
            summaries = self._run_store.list_runs(limit=200)
            for s in summaries:
                if s.get("conversation_id") == conversation_id:
                    run_id = s.get("run_id", "")
                    if run_id:
                        return self.get_run(run_id)
        return None
