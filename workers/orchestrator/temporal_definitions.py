from __future__ import annotations

from datetime import timedelta
from typing import Any

try:
    from temporalio import activity, workflow
except ModuleNotFoundError:  # pragma: no cover
    activity = None
    workflow = None


if workflow is not None and activity is not None:

    @activity.defn
    def execute_friday_run_activity(payload: dict[str, Any]) -> dict[str, Any]:
        from workers.orchestrator.temporal_runtime import run_handler

        return run_handler(payload)


    @workflow.defn
    class FridayRunWorkflow:
        @workflow.run
        async def run(self, payload: dict[str, Any]) -> dict[str, Any]:
            return await workflow.execute_activity(
                execute_friday_run_activity,
                payload,
                start_to_close_timeout=timedelta(minutes=15),
            )

else:

    def execute_friday_run_activity(payload: dict[str, Any]) -> dict[str, Any]:  # pragma: no cover
        raise RuntimeError("temporalio is not installed")


    class FridayRunWorkflow:  # pragma: no cover
        pass
