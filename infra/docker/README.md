# Docker Local Stack

`infra/docker/docker-compose.yml` provides local infrastructure services with health checks:
- Postgres (`pgvector/pgvector:pg16`) on `localhost:5432`
- Redis on `localhost:6379`
- Temporal on `localhost:7233`
- Temporal UI on `localhost:8088`

## One-command startup
From repo root:

```bash
scripts/dev_up.sh
```

This command:
- starts Docker infra
- waits for Temporal health
- starts the FastAPI app
- starts the Temporal worker

To stop infra containers:

```bash
scripts/dev_down.sh
```
