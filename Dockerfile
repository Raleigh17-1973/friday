# ─── Stage 1: builder ────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /app

# System deps needed for psycopg binary + pypdf native build tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy only what's needed for pip install so Docker layer cache is reused
# when source changes but deps don't
COPY pyproject.toml ./
# Minimal stub so pip -e works without the full source tree
RUN mkdir -p packages/agents packages/common packages/llm packages/memory \
             packages/governance packages/tools packages/observability \
             workers/orchestrator workers/evals workers/reflection \
             apps/api apps/web scripts src \
    && touch packages/__init__.py workers/__init__.py apps/__init__.py

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e ".[phase3,phase4]"

# ─── Stage 2: runtime ────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

# Runtime system libs only (libpq for psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Non-root user
RUN groupadd -r friday && useradd -r -g friday friday

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application source
COPY --chown=friday:friday . .

# Create data directory for SQLite fallback (overridden by DATABASE_URL in production)
RUN mkdir -p data && chown friday:friday data

USER friday

EXPOSE 8000

# Default: single worker. Override with WEB_CONCURRENCY or --workers for multi-core.
CMD ["python", "-m", "uvicorn", "apps.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", \
     "--log-level", "info"]
