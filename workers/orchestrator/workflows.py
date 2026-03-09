from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4


@dataclass
class WorkflowRecord:
    workflow_id: str
    status: str
    payload: dict[str, Any]
    result: dict[str, Any] | None


class InProcessWorkflowEngine:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                create table if not exists workflows (
                  workflow_id text primary key,
                  status text not null,
                  payload text not null,
                  result text,
                  created_at text default current_timestamp
                )
                """
            )

    def run(self, payload: dict[str, Any], execute_fn) -> WorkflowRecord:
        import json

        workflow_id = f"wf_{uuid4().hex[:12]}"
        with self._connect() as conn:
            conn.execute(
                "insert into workflows(workflow_id, status, payload, result) values (?, ?, ?, ?)",
                (workflow_id, "running", json.dumps(payload), None),
            )

        try:
            result = execute_fn(payload)
            status = "completed"
        except Exception as exc:  # pragma: no cover
            result = {"error": str(exc)}
            status = "failed"

        with self._connect() as conn:
            conn.execute(
                "update workflows set status = ?, result = ? where workflow_id = ?",
                (status, json.dumps(result), workflow_id),
            )

        return WorkflowRecord(workflow_id=workflow_id, status=status, payload=payload, result=result)

    def get(self, workflow_id: str) -> WorkflowRecord | None:
        import json

        with self._connect() as conn:
            row = conn.execute(
                "select workflow_id, status, payload, result from workflows where workflow_id = ?",
                (workflow_id,),
            ).fetchone()
        if row is None:
            return None
        return WorkflowRecord(
            workflow_id=row["workflow_id"],
            status=row["status"],
            payload=json.loads(row["payload"]),
            result=json.loads(row["result"]) if row["result"] else None,
        )


class TemporalWorkflowEngine:
    def __init__(
        self,
        *,
        address: str,
        namespace: str,
        task_queue: str,
    ) -> None:
        self._address = address
        self._namespace = namespace
        self._task_queue = task_queue

    def run(self, payload: dict[str, Any], execute_fn) -> WorkflowRecord:
        import asyncio

        del execute_fn  # run is executed by Temporal worker activity.

        async def _start() -> WorkflowRecord:
            try:
                from temporalio.client import Client
                from temporalio.common import WorkflowIDReusePolicy
            except ModuleNotFoundError as exc:  # pragma: no cover
                raise RuntimeError("temporalio is required for TemporalWorkflowEngine") from exc

            from workers.orchestrator.temporal_definitions import FridayRunWorkflow

            client = await Client.connect(self._address, namespace=self._namespace)
            workflow_id = f"wf_{uuid4().hex[:12]}"
            await client.start_workflow(
                FridayRunWorkflow.run,
                payload,
                id=workflow_id,
                task_queue=self._task_queue,
                id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
            )
            return WorkflowRecord(workflow_id=workflow_id, status="running", payload=payload, result=None)

        return asyncio.run(_start())

    def get(self, workflow_id: str) -> WorkflowRecord | None:
        import asyncio

        async def _get() -> WorkflowRecord | None:
            try:
                from temporalio.client import Client
                from temporalio.service import RPCError
            except ModuleNotFoundError as exc:  # pragma: no cover
                raise RuntimeError("temporalio is required for TemporalWorkflowEngine") from exc

            client = await Client.connect(self._address, namespace=self._namespace)
            handle = client.get_workflow_handle(workflow_id)
            try:
                desc = await handle.describe()
            except RPCError:
                return None

            status_name = str(desc.status.name).lower()
            if status_name == "running":
                return WorkflowRecord(workflow_id=workflow_id, status="running", payload={}, result=None)
            if status_name == "completed":
                result = await handle.result()
                return WorkflowRecord(workflow_id=workflow_id, status="completed", payload={}, result=result)
            return WorkflowRecord(workflow_id=workflow_id, status=status_name, payload={}, result=None)

        return asyncio.run(_get())
