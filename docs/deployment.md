# Web Radar — Production Deployment & Operations Runbook

This runbook documents the deployment architecture, configuration variables, migration commands, and operational procedures for running Web Radar in production.

---

## 1. System Architecture

```
[ Web Browser ]
      │
      ▼
[ Next.js 15 Frontend (Vercel) ]
      │  (HTTPS JSON API)
      ▼
[ FastAPI Backend (Hugging Face Spaces / Render / Docker) ]
      │
      ├──▶ [ Neon PostgreSQL ] (Authoritative persistent source of truth)
      ├──▶ [ Bright Data Scraper Studio ] (c_msz0zrtw29tjzhzakl custom scrapers)
      └──▶ [ Google Gemini AI ] (Natural-language Watch planner)
```

- **Frontend & Backend are independently deployable**.
- **The backend and Neon PostgreSQL are the authoritative source of truth**. The browser never owns scheduling or monitoring state; all Watches, Runs, Snapshots, Changes, and Alerts persist indefinitely in Neon DB.

---

## 2. Environment Variables

### Backend Configuration (`backend/.env` or Platform Environment Secrets)

| Variable | Description | Default / Example | Required? |
| :--- | :--- | :--- | :--- |
| `DATABASE_URL` | Neon PostgreSQL connection URI with SSL | `postgresql+psycopg://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require` | **Yes** |
| `BRIGHT_DATA_API_KEY` | Bright Data API Bearer Token | `b4a2...` | **Yes** (in production) |
| `BRIGHT_DATA_COLLECTOR_ID` | Custom Scraper Studio Collector ID | `c_msz0zrtw29tjzhzakl` | **Yes** |
| `GEMINI_API_KEY` | Google AI Studio API Key | `AIzaSy...` | **Yes** (in production) |
| `GEMINI_MODEL` | Gemini LLM model for natural-language planner | `gemini-2.5-flash` | No |
| `CORS_ORIGINS` | Allowed frontend domains (comma-separated or JSON list) | `http://localhost:3000,https://*.vercel.app` | No |
| `SCHEDULER_ENABLED` | Run autonomous background scheduler in API lifespan | `true` | No |
| `SCHEDULER_POLL_INTERVAL_SECONDS` | Interval between scheduler claim cycles | `10.0` | No |
| `APP_ENV` | Application environment identifier | `production` | No |
| `LOG_LEVEL` | Logging verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) | `INFO` | No |

### Frontend Configuration (`frontend/.env.local` or Vercel Environment Variables)

| Variable | Description | Example | Required? |
| :--- | :--- | :--- | :--- |
| `NEXT_PUBLIC_API_BASE_URL` | Public HTTPS URL of the FastAPI backend (no trailing slash) | `https://api.webradar.io` or `https://username-webradar.hf.space` | **Yes** |

> [!CAUTION]
> Never prefix backend secret keys (`DATABASE_URL`, `BRIGHT_DATA_API_KEY`, `GEMINI_API_KEY`) with `NEXT_PUBLIC_`. All Bright Data and LLM operations remain strictly behind the backend integration boundary.

---

## 3. Database Setup & Migrations

Web Radar uses immutable SQL migrations with SHA-256 checksum verification stored in `schema_migrations`.

### Running Migrations

Before launching the backend container or web service:

```bash
# From workspace root
python database/migrate.py
```

Or on PowerShell:
```powershell
.\database\migrate.ps1
```

Migrations applied:
1. `001_initial_schema.sql` (Users, Watches, Schedules, Scrapers)
2. `002_watch_runs_and_snapshots.sql` (WatchRuns, Snapshots, Changes)
3. `003_bright_data_execution.sql` (Bright Data collection correlation)
4. `004_semantic_alerts.sql` (Deterministic alert events and rules)
5. `005_scraper_repairs.sql` (Self-healing repair lifecycle tracking)

---

## 4. Backend Deployment Guide

### Option A: Hugging Face Spaces (Docker SDK + GitHub Actions CI/CD)

#### 1. Create the Hugging Face Space
1. Go to [huggingface.co/new-space](https://huggingface.co/new-space).
2. Choose **Docker** as the Space SDK (Blank template).
3. Set Space Name (e.g. `web-radar-api`).

#### 2. Configure GitHub Secrets & Variables

In your GitHub Repo **Settings** $\rightarrow$ **Secrets and variables** $\rightarrow$ **Actions**:

1. **Repository Secret** (under **Secrets** tab):
   - **Name**: `HF_TOKEN`
   - **Value**: Create a **Write** token on [huggingface.co/settings/tokens](https://huggingface.co/settings/tokens) and paste it here.
2. **Repository Variable** (under **Variables** tab):
   - **Name**: `HF_SPACE`
   - **Value**: `<your-hf-username>/<your-space-name>` (e.g. `harisawan27/web-radar-api`)

#### 3. Configure Space Secrets & Variables
In your Hugging Face Space **Settings** $\rightarrow$ **Variables and secrets**:
- **Secrets**:
  - `DATABASE_URL`: `postgresql+psycopg://user:password@ep-xyz.aws.neon.tech/neondb?sslmode=require`
  - `BRIGHT_DATA_API_KEY`: Your Bright Data API Key
  - `BRIGHT_DATA_COLLECTOR_ID`: `c_msz0zrtw29tjzhzakl`
  - `GEMINI_API_KEY`: Your Google AI Studio Gemini API Key
- **Variables**:
  - `CORS_ORIGINS`: `http://localhost:3000,https://your-frontend.vercel.app`
  - `SCHEDULER_ENABLED`: `true`

Every push to `main` affecting `backend/`, `database/`, or `Dockerfile` will automatically sync and build your backend on Hugging Face Spaces via `.github/workflows/deploy-backend.yml`!



### Option B: Render / Railway / VM

1. **Build Command**: `pip install -e backend`
2. **Pre-Deploy Migration Command**: `python database/migrate.py`
3. **Start Command**: `uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port $PORT`

---

## 5. Frontend Deployment Guide (Vercel)

1. Connect the GitHub repository to **Vercel**.
2. Set the **Root Directory** to `frontend`.
3. Add the **Environment Variable**:
   - `NEXT_PUBLIC_API_BASE_URL`: `https://your-backend.hf.space` (or custom API domain)
4. Deploy! Vercel will run:
   - `npm install`
   - `npm run build`

---

## 6. Worker & Autonomous Scheduling Strategy

Web Radar supports two operational modes for background monitoring:

1. **Embedded Lifespan Runner (Default)**:
   - The FastAPI backend starts `AsyncSchedulerRunner` during application startup (`lifespan`).
   - Discovers due watches, claims them with `SELECT ... FOR UPDATE SKIP LOCKED` (safe for multi-replica concurrency), and polls active Bright Data jobs.
2. **Dedicated Background Worker Container**:
   - Run `python -m app.worker` as an independent service or worker dyno.
   - Set `SCHEDULER_ENABLED=false` on the web dynos and `SCHEDULER_ENABLED=true` on the worker dyno.

---

## 7. Health & Monitoring Endpoints

- `GET /health` — Fast liveness probe (returns `{"status": "ok"}`). Used for load balancer health checks.
- `GET /health/database` — Readiness probe (verifies active Neon PostgreSQL query execution).
- `GET /v1/scheduler/status` — Status probe for background scheduler loop.
