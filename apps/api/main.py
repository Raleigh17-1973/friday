from __future__ import annotations

import os
import pathlib
from typing import Any, Optional

# PR-09: Load .env only outside production — in production all config must come from
# the real environment (injected by the container/orchestrator), not a dotenv file.
_ROOT = pathlib.Path(__file__).resolve().parents[2]
_ENV = os.getenv("ENV", "local")
if _ENV != "production":
    _dotenv = _ROOT / ".env"
    if _dotenv.exists():
        with _dotenv.open() as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _, _v = _line.partition("=")
                    os.environ.setdefault(_k.strip(), _v.strip())

from apps.api.deps import service, admin_auth, rate_limiter, upload_store as _UPLOAD_STORE_REF
from apps.api.security import AuthContext, resolve_auth, PUBLIC_PATHS

try:
    from fastapi import FastAPI, File, HTTPException, Request, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import JSONResponse, FileResponse, StreamingResponse
    from fastapi.staticfiles import StaticFiles
    from pydantic import BaseModel
except ModuleNotFoundError as exc:  # pragma: no cover
    raise RuntimeError(
        "FastAPI is required for apps/api/main.py. Install project dependencies first."
    ) from exc

app = FastAPI(title="Friday API", version="0.2.0")

# PR-09: CORS — production requires explicit FRIDAY_ALLOWED_ORIGINS; dev falls back to localhost
_raw_origins = os.getenv("FRIDAY_ALLOWED_ORIGINS", "")
if not _raw_origins:
    if _ENV == "production":
        raise RuntimeError(
            "FRIDAY_ALLOWED_ORIGINS must be set in production (comma-separated list of allowed origins)"
        )
    _raw_origins = "http://localhost:3000,http://127.0.0.1:3000,http://127.0.0.1:8000"
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_UI_DIR = pathlib.Path(__file__).parent.parent.parent / "ui"
if _UI_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(_UI_DIR / "assets")), name="static")

    @app.get("/")
    def serve_ui():
        return FileResponse(str(_UI_DIR / "index.html"))

# Alias upload_store to the module-level name for backward-compatibility with
# existing route handlers in this file.  Router modules will import from deps directly.
_UPLOAD_STORE = _UPLOAD_STORE_REF


@app.middleware("http")
async def add_security_and_limits(request: Request, call_next):
    # PR-01: Authentication — resolve caller identity, reject unknown keys.
    path = request.url.path

    if len(path) > 2048:
        return JSONResponse({"detail": "path too long"}, status_code=414)

    auth_ctx = resolve_auth(request)
    if auth_ctx is None:
        return JSONResponse({"detail": "authentication required"}, status_code=401)

    # Make identity available to route handlers without changing every signature.
    request.state.auth = auth_ctx

    # PR-04: Rate limit keyed by (org_id, user_id) when authenticated, else by IP.
    if path not in PUBLIC_PATHS and not path.startswith("/static"):
        rate_key = f"{auth_ctx.org_id}:{auth_ctx.user_id}"
        rate_limiter.check(rate_key, path)

    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    return response


# Router imports and includes
from apps.api.routes import (
    chat,
    runs,
    governance,
    conversations,
    tasks,
    admin,
    files,
    okrs,
    processes,
    workspaces,
    org,
    finance,
    qa,
    integrations,
    proactive,
)

app.include_router(chat.router)
app.include_router(runs.router)
app.include_router(governance.router)
app.include_router(conversations.router)
app.include_router(tasks.router)
app.include_router(admin.router)
app.include_router(files.router)
app.include_router(okrs.router)
app.include_router(processes.router)
app.include_router(workspaces.router)
app.include_router(org.router)
app.include_router(finance.router)
app.include_router(qa.router)
app.include_router(integrations.router)
app.include_router(proactive.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict:
    """Readiness probe — checks that all critical dependencies are reachable.

    Used by Fly.io health checks and Kubernetes readiness probes.
    Returns 200 when the service can accept traffic, 503 when not ready.
    """
    checks: dict[str, str] = {}
    ok = True

    # Memory / DB connectivity
    try:
        # Lightweight check: just verify the memory service is initialised
        _ = service.memory  # would raise if initialisation failed
        checks["memory"] = "ok"
    except Exception as exc:
        checks["memory"] = f"error: {exc}"
        ok = False

    # Agent registry
    try:
        agents = service.registry.list_active()
        checks["registry"] = f"ok ({len(agents)} agents)"
    except Exception as exc:
        checks["registry"] = f"error: {exc}"
        ok = False

    # LLM provider (advisory — does not block readiness)
    checks["llm"] = "connected" if service.llm is not None else "offline (stub mode)"

    status_code = 200 if ok else 503
    return JSONResponse(
        content={"status": "ready" if ok else "degraded", "checks": checks},
        status_code=status_code,
    )
