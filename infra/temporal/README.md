# Temporal Integration

Current implementation includes:
- Temporal workflow definition: `workers/orchestrator/temporal_definitions.py`
- Temporal run handler wiring: `workers/orchestrator/temporal_runtime.py`
- Temporal-aware engine: `workers/orchestrator/workflows.py`
- Worker entrypoint: `scripts/run_temporal_worker.py`

## Configure API to use Temporal
Set environment variables before starting API:
- `FRIDAY_WORKFLOW_ENGINE=temporal`
- `TEMPORAL_ADDRESS=localhost:7233`
- `TEMPORAL_NAMESPACE=default`
- `TEMPORAL_TASK_QUEUE=friday-runs`

## Run worker
```bash
PYTHONPATH=. python3 scripts/run_temporal_worker.py
```

Notes:
- API submits workflows to Temporal and returns workflow IDs.
- Worker executes `FridayRunWorkflow` and runs the Friday payload activity.
