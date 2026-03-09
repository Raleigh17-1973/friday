# Friday

Friday is a modular multi-agent business assistant.

## Included in v1
- Domain agents (Sales, Support, HR, IT, Engineering, Finance, Legal, Communications, Strategy, Product, PMO, Analytics, Security, Procurement, Ops, RevOps, Executive CoS, QA Critic, GRC)
- Dynamic router/classifier
- Orchestrator with memory/state context
- Minimal web chat UI
- Basic tests

## Run

```bash
PYTHONPATH=src python3 chat_server.py
```

Open `http://127.0.0.1:8000`.

## Test

```bash
PYTHONPATH=src python3 -m pytest -q
```
