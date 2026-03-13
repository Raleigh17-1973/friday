# Friday — Deployment Guide

This guide covers the full production stack: **Supabase** (Postgres + pgvector) → **Fly.io** (API) → **Vercel** (web UI).

Estimated time: 30–45 minutes for a first deploy.

---

## Prerequisites

| Tool | Install |
|---|---|
| [flyctl](https://fly.io/docs/hands-on/install-flyctl/) | `brew install flyctl` or `curl -L https://fly.io/install.sh \| sh` |
| [Vercel CLI](https://vercel.com/docs/cli) | `npm i -g vercel` |
| Python 3.11+ | already required for local dev |
| Docker (optional) | only needed to test the container locally |

---

## 1. Supabase — Database Setup

1. Create a free account at [supabase.com](https://supabase.com) and create a new project.

2. In your project dashboard → **Settings → Database**, copy the **Connection string (URI)** for the connection pooler (port 6543, Transaction mode). It looks like:
   ```
   postgresql://postgres.[project-ref]:[password]@aws-0-us-east-1.pooler.supabase.com:6543/postgres
   ```

3. Enable `pgvector`:
   ```sql
   -- Run in Supabase SQL Editor
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

4. You will use this URL for both `FRIDAY_MEMORY_DATABASE_URL` and `FRIDAY_AUDIT_DATABASE_URL` (or separate projects if you want isolated schemas).

---

## 2. Fly.io — API Deployment

### 2a. Sign up and authenticate
```bash
flyctl auth signup   # or: flyctl auth login
```

### 2b. Create the app (first deploy only)
```bash
cd /path/to/friday
flyctl launch --no-deploy --name friday-api --region iad
```
This writes `fly.toml` (already committed). Skip if you already have it.

### 2c. Set secrets
```bash
flyctl secrets set \
  ANTHROPIC_API_KEY="sk-ant-..." \
  OPENAI_API_KEY="sk-proj-..." \
  FRIDAY_MEMORY_DATABASE_URL="postgresql://postgres.[ref]:[pw]@aws-...pooler.supabase.com:6543/postgres" \
  FRIDAY_AUDIT_DATABASE_URL="postgresql://postgres.[ref]:[pw]@aws-...pooler.supabase.com:6543/postgres" \
  FRIDAY_ALLOWED_ORIGINS="https://your-app.vercel.app" \
  ADMIN_API_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
```

> **Tip:** `FRIDAY_ALLOWED_ORIGINS` must match your Vercel deployment URL exactly (no trailing slash).
> You can update it after Vercel is set up:
> `flyctl secrets set FRIDAY_ALLOWED_ORIGINS="https://friday-abc123.vercel.app"`

### 2d. Deploy
```bash
flyctl deploy
```
This builds the Docker image, pushes it, and deploys. Takes ~3 minutes.

### 2e. Verify
```bash
flyctl status                     # check machines are running
curl https://friday-api.fly.dev/health  # should return {"status":"ok"}
curl https://friday-api.fly.dev/ready   # should return {"status":"ready"}
```

### 2f. View logs
```bash
flyctl logs
```

---

## 3. Vercel — Web UI Deployment

### 3a. Link the project
```bash
cd /path/to/friday
vercel link
```
Or import from the [Vercel dashboard](https://vercel.com/new) → select your GitHub repo.

### 3b. Configure environment variables
In the Vercel dashboard → **Project → Settings → Environment Variables**, add:

| Variable | Value |
|---|---|
| `FRIDAY_BACKEND_URL` | `https://friday-api.fly.dev` |
| `OPENAI_API_KEY` | `sk-proj-...` *(only if using ChatKit SDK)* |

Or via CLI:
```bash
vercel env add FRIDAY_BACKEND_URL production
# paste: https://friday-api.fly.dev
```

### 3c. Deploy
```bash
vercel --prod
```
Or push to `main` — Vercel auto-deploys on every push.

### 3d. Update Fly.io CORS
After Vercel gives you a URL (e.g., `https://friday-abc123.vercel.app`):
```bash
flyctl secrets set FRIDAY_ALLOWED_ORIGINS="https://friday-abc123.vercel.app"
```

---

## 4. GitHub Actions CI/CD (optional but recommended)

The workflows in `.github/workflows/` automate tests and deployment:

| Workflow | Trigger | What it does |
|---|---|---|
| `ci.yml` | Every push + PR | pytest, pyright, Docker build |
| `deploy-api.yml` | Push to `main` | Deploy to Fly.io (after tests pass) |

### Setup

1. Go to your GitHub repo → **Settings → Secrets and variables → Actions**

2. Add these repository secrets:
   - `FLY_API_TOKEN` — get it with: `flyctl auth token`

3. Create a **production** environment (for deploy gate):
   **Settings → Environments → New environment → name it `production`**

4. Push to `main` — the deploy workflow will run automatically.

---

## 5. Local Docker Testing

Before deploying, you can test the production container locally:

```bash
# Build
docker build -t friday-api .

# Run
docker run -p 8000:8000 \
  -e ANTHROPIC_API_KEY="sk-ant-..." \
  -e OPENAI_API_KEY="sk-proj-..." \
  friday-api

# Test
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

### Full stack with Docker Compose
```bash
# Copy env
cp .env.example .env
# Fill in .env values

cd infra/docker
docker compose up --build
```

Services:
- API: http://localhost:8000
- Web: http://localhost:3000
- Postgres: localhost:5432

---

## 6. Environment Variables Reference

See `.env.example` for the full list. Production must-haves:

| Variable | Required | Notes |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes (or OpenAI) | Primary LLM |
| `OPENAI_API_KEY` | Yes (or Anthropic) | Fallback + embeddings + vision |
| `FRIDAY_MEMORY_DATABASE_URL` | Recommended | Supabase/Postgres connection string |
| `FRIDAY_AUDIT_DATABASE_URL` | Recommended | Can be same as memory URL |
| `FRIDAY_ALLOWED_ORIGINS` | Yes | Your Vercel URL |
| `ADMIN_API_KEY` | Yes | For `/admin/dashboard` |
| `FRIDAY_BACKEND_URL` | Yes (web) | Set in Vercel env vars |

---

## 7. Cost Estimate

| Layer | Service | Free Tier | Paid |
|---|---|---|---|
| API | Fly.io | 3 shared-CPU VMs | ~$7/mo |
| Web | Vercel | 100GB bandwidth | $20/mo (Pro) |
| Database | Supabase | 500MB + 2 projects | $25/mo (Pro) |
| LLM | OpenAI / Anthropic | Pay per token | ~$5–50/mo |
| **Total** | | **~$0/mo** | **~$57/mo** |

For personal/demo use, the free tiers of Fly.io + Vercel + Supabase cover most usage.

---

## 8. Troubleshooting

**API cold start is slow (~5s)**
Set `min_machines_running = 1` in `fly.toml` to keep one machine always warm.

**`/ready` returns 503**
The API is still initializing or the database connection failed. Check `flyctl logs` for the error.

**CORS errors in browser**
`FRIDAY_ALLOWED_ORIGINS` on Fly.io doesn't match the Vercel URL exactly. Update with:
```bash
flyctl secrets set FRIDAY_ALLOWED_ORIGINS="https://your-exact-vercel-url.vercel.app"
```

**Vercel build fails**
Ensure `FRIDAY_BACKEND_URL` is set in Vercel environment variables before building.

**File uploads fail**
The `/upload` endpoint requires `python-multipart` (included in core deps). For PDF support, ensure `pypdf` is installed (included in `phase4` optional deps, which the Dockerfile installs via `.[phase3,phase4]`).
