from __future__ import annotations

import asyncio
import os

from apps.api.service import FridayService
from workers.orchestrator.temporal_definitions import FridayRunWorkflow, execute_friday_run_activity
from workers.orchestrator.temporal_runtime import configure_run_handler


async def main() -> None:
    try:
        from temporalio.client import Client
        from temporalio.worker import Worker
    except ModuleNotFoundError as exc:  # pragma: no cover
        raise RuntimeError("temporalio is required to run Temporal worker") from exc

    service = FridayService()

    def _run_payload(payload: dict) -> dict:
        return service.execute_chat_payload(payload)

    configure_run_handler(_run_payload)

    temporal_address = os.getenv("TEMPORAL_ADDRESS", "localhost:7233")
    namespace = os.getenv("TEMPORAL_NAMESPACE", "default")
    task_queue = os.getenv("TEMPORAL_TASK_QUEUE", "friday-runs")

    client = await Client.connect(temporal_address, namespace=namespace)
    worker = Worker(
        client,
        task_queue=task_queue,
        workflows=[FridayRunWorkflow],
        activities=[execute_friday_run_activity],
    )
    await worker.run()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
