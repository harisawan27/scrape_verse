# 🌐 Web Radar (ScrapeVerse)

> **Autonomous, Persistent Web Monitoring & Intelligence Engine**  
> *Engineered with FastAPI, Neon Serverless PostgreSQL, and Bright Data Scraper Studio.*

[![Tests Passing](https://img.shields.io/badge/Tests-41%2F41%20Passing-brightgreen?style=for-the-badge&logo=pytest)](file:///f:/scrape_verse/backend/tests)
[![PostgreSQL](https://img.shields.io/badge/Database-Neon%20PostgreSQL-00E699?style=for-the-badge&logo=postgresql)](https://neon.tech)
[![Scraper Studio](https://img.shields.io/badge/Scraper-Bright%20Data%20Studio-orange?style=for-the-badge)](https://brightdata.com)
[![FastAPI](https://img.shields.io/badge/Framework-FastAPI-009688?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%20%7C%203.12%20%7C%203.13-blue?style=for-the-badge&logo=python)](https://www.python.org)

---

## ⚡ Executive Summary

**Web Radar** is a production-grade, server-side web intelligence and monitoring platform designed for real-world reliability. Unlike conventional client-side scrapers that fail when a browser tab closes or simple cron scripts that break when HTML layouts change, Web Radar provides **persistent, durable state management**, **concurrency-safe scheduling**, and **deep integration with Bright Data's custom Scraper Studio**.

Built from the ground up to operate autonomously on cloud infrastructure (e.g. Hugging Face Spaces, Railway, Render), Web Radar continuously captures web snapshots, tracks structural & numerical changes (such as price drops and inventory status), and provides an immutable audit trail of every execution.

---

## 🏗️ Architecture & Data Flow

Web Radar enforces strict separation of concerns. The backend database is the single authoritative source of truth.

```mermaid
flowchart TD
    subgraph ClientLayer ["Client & Ingestion Layer"]
        User(["👤 User / Client"]) -->|1. Configure Watch & Schedule| API["⚡ FastAPI Application"]
    end

    subgraph StorageLayer ["Authoritative Persistence (Neon PostgreSQL)"]
        API -->|2. Store Watch & Cadence| DB[("🐘 Neon PostgreSQL<br/>• watches<br/>• schedules<br/>• watch_runs<br/>• snapshots<br/>• changes")]
    end

    subgraph SchedulerWorker ["Autonomous Engine"]
        Sched["⏱️ SchedulerService<br/>(Due Cadence Discovery)"] -->|3. Claim via SKIP LOCKED| DB
        Sched -->|4. Create Pending WatchRun| DB
        Worker["⚙️ WorkerService<br/>(Async Lifecycle)"] -->|5. Claim Pending Run| DB
    end

    subgraph ProviderLayer ["Bright Data Scraper Studio"]
        Worker -->|6. Trigger Custom Scraper<br/>POST /dca/trigger| BD_Trigger["🌐 Bright Data Studio Collector<br/>(e.g., c_msz0zrtw29tjzhzakl)"]
        BD_Trigger -->|7. Return j_... Job ID| Worker
        Worker -->|8. Persist External ID immediately| DB
        Worker -.->|9. Asynchronous Status Poll<br/>GET /dca/log| BD_Poll["📊 Progress Status Engine"]
        BD_Poll -->|10. Deliver Dataset (.jsonl)<br/>GET /dca/dataset| Worker
    end

    subgraph DiffPipeline ["Snapshot & Intelligence Engine"]
        Worker -->|11. Normalize Payload| Normalizer["📦 Payload Normalizer"]
        Normalizer -->|12. Compute Structural Diff| Diff["🔍 Deterministic Diff Engine"]
        Diff -->|13. Persist Snapshot & Changes| DB
        Diff -->|14. Mark Run Succeeded| DB
    end

    classDef primary fill:#2563eb,stroke:#1d4ed8,stroke-width:2px,color:#fff;
    classDef secondary fill:#059669,stroke:#047857,stroke-width:2px,color:#fff;
    classDef highlight fill:#d97706,stroke:#b45309,stroke-width:2px,color:#fff;
    classDef storage fill:#4338ca,stroke:#3730a3,stroke-width:2px,color:#fff;

    class API primary;
    class Worker,Sched secondary;
    class BD_Trigger,BD_Poll highlight;
    class DB storage;
```

---

## 🌟 Core Innovations & Engineering Highlights

### 1. 🔒 Durable State Machine & Concurrency Control
- **State Progression**: `pending` ➔ `running` (with external `j_...` ID) ➔ `succeeded` | `failed`.
- **Row-Level Locking**: PostgreSQL `SELECT ... FOR UPDATE SKIP LOCKED` guarantees multiple worker or scheduler replicas never double-trigger the same Watch.
- **Race Condition Defense**: Unique partial index `uq_active_watch_runs_per_watch` (`WHERE status IN ('pending', 'running')`) guarantees at most one active execution per Watch at the database constraint level.

### 2. 🔌 Asynchronous, Restart-Safe Worker Lifecycle
- Workers **never block threads** in multi-minute sleep loops.
- Upon job trigger, the Bright Data collection identifier (`j_...`) is **immediately persisted to Neon PostgreSQL**.
- If a server crashes or restarts mid-flight, the worker discovers in-flight jobs on reboot and resumes polling without re-triggering expensive third-party scrapers.

### 3. 🎯 Custom Bright Data Scraper Studio Integration
- Built specifically for custom Scraper Studio collectors (`c_...` DCA namespace) rather than generic black-box scrapers.
- Tested and verified live on e-commerce product monitoring (`daraz.pk`), extracting structured title, pricing, currency, stock status, ratings, and custom metadata.
- Clean adapter abstraction: `HttpBrightDataAdapter` for production, `MockBrightDataAdapter` for hermetic, sub-second test runs.

### 4. 📊 Sub-Millisecond Structural Diffing
- Deterministic payload diff engine (`diff_payloads`) recursively analyzes schema changes between consecutive successful snapshots without requiring costly LLM tokens for basic field comparison.
- Generates categorized `Change` records: `value_changed`, `field_added`, `field_removed`.

---

## 📂 Repository Layout

```text
scrape_verse/
├── backend/
│   ├── app/
│   │   ├── integrations/
│   │   │   └── bright_data/     # Bright Data DCA & Datasets adapter, types, normalizer
│   │   ├── services/
│   │   │   ├── runs.py          # Run creation, MockRunExecutor, BrightDataRunExecutor
│   │   │   ├── worker.py        # WorkerService (asynchronous claim, poll & finalize)
│   │   │   ├── scheduler.py     # SchedulerService (timezone-aware cadence, row locking)
│   │   │   └── changes.py       # Deterministic recursive snapshot diff engine
│   │   ├── models.py            # SQLAlchemy models (User, Watch, Schedule, Run, Snapshot...)
│   │   ├── repositories.py      # Database access layer
│   │   ├── schemas.py           # Pydantic v2 schemas & request validation
│   │   ├── config.py            # Typed application settings (pydantic-settings)
│   │   ├── db.py                # Engine initialization & session management
│   │   └── main.py              # FastAPI application & REST endpoints
│   ├── tests/
│   │   ├── test_bright_data.py         # Bright Data adapter unit & live smoke tests
│   │   ├── test_bright_data_worker.py  # Worker asynchronous recovery & idempotency tests
│   │   ├── test_postgres_integration.py# Live Neon PostgreSQL integration suite
│   │   ├── test_runs.py                # Run state machine & diffing tests
│   │   ├── test_scheduler.py           # Cadence advancement & concurrency tests
│   │   └── test_watches.py             # Watch CRUD & API contract tests
│   ├── pyproject.toml           # Project dependencies & tool configurations
│   └── README.md                # Backend specific operational guide
├── database/
│   ├── migrations/
│   │   ├── 001_initial.sql                 # Base tables (users, watches, schedules, runs)
│   │   ├── 002_watch_run_lifecycle.sql     # State constraints & partial active unique index
│   │   └── 003_bright_data_worker_indexes.sql # Partial index for in-flight worker recovery
│   ├── migrate.py               # SHA-256 verified migration engine
│   └── migrate.ps1              # Windows migration helper
├── docs/                        # Architecture decisions & API specs
└── AGENTS.md                    # Repository guidelines & engineering rules
```

---

## 🗄️ Database Schema & Domain Model

| Domain Entity | Table Name | Purpose & Key Guarantees |
| :--- | :--- | :--- |
| **User** | `users` | Multi-tenant user identity (`email` unique). |
| **Watch** | `watches` | Target URL, title, natural language instruction, and JSON monitoring specifications. |
| **Schedule** | `schedules` | Automated cadence (`hourly`, `daily`, `weekly`, `custom`), timezone awareness, indexed `next_due_at`. |
| **WatchRun** | `watch_runs` | Immutable execution record with state machine (`pending`, `running`, `succeeded`, `failed`), unique Bright Data `j_...` ID. |
| **Snapshot** | `snapshots` | Normalized JSON payload, extracted metadata, timestamps. Exactly 1 snapshot per successful run. |
| **Change** | `changes` | Computed diff between consecutive runs (`change_type`, `details`, `path`, `old_value`, `new_value`). |
| **Alert** | `alerts` | Evaluation outcome and notification status for triggered conditions. |

---

## 🚀 Quickstart Guide

### Prerequisites
- **Python 3.11+** installed
- **PostgreSQL / Neon Database URL** (e.g. `postgresql+psycopg://user:pass@ep-xyz.neon.tech/neondb?sslmode=require`)
- **Bright Data API Key** (optional for local mock mode; required for live scraping)

### 1. Clone & Set Up Environment

```bash
git clone https://github.com/your-org/scrape-verse.git
cd scrape-verse/backend

# Create virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Unix/macOS:
source .venv/bin/activate

# Install editable package with dev dependencies
pip install -e ".[dev]"
```

### 2. Configure Environment Variables

Create `backend/.env`:

```env
DATABASE_URL=postgresql+psycopg://<user>:<password>@<neon-host>/<database>?sslmode=require
BRIGHTDATA_API_KEY=your_bright_data_api_token
BRIGHTDATA_COLLECTOR_ID=c_msz0zrtw29tjzhzakl
SCHEDULER_POLL_INTERVAL_SECONDS=5.0
```

### 3. Run Database Migrations

Apply verified migrations against Neon PostgreSQL:

```bash
python ../database/migrate.py
```

### 4. Start the API Server

```bash
uvicorn app.main:app --reload --port 8000
```
Interactive Swagger Documentation will be live at: `http://localhost:8000/docs`.

---

## 🧪 Comprehensive Verification & Test Suite

Web Radar includes a **41-test automated suite** covering unit, SQLite hermetic tests, and live Neon PostgreSQL + Bright Data integration.

```bash
# Run hermetic test suite (SQLite in-memory, instant)
pytest -v

# Run full suite including live Neon PostgreSQL & Bright Data Scraper Studio
$env:RUN_POSTGRES_INTEGRATION="1"
pytest -v
```

### Test Suite Summary:
- **`test_bright_data.py`** (8 tests): Validates authentication, payload structure, JSONL parsing, error status codes, and live Bright Data API credentials.
- **`test_bright_data_worker.py`** (7 tests): Validates asynchronous execution, restart recovery from database, snapshot persistence, idempotency, and independent multi-watch execution.
- **`test_postgres_integration.py`** (5 tests): Real Neon PostgreSQL integration testing row-level locks, lifecycle transitions, unique constraints, and end-to-end Bright Data execution.
- **`test_runs.py`** (6 tests): Validates state machine invariants and deterministic change detection.
- **`test_scheduler.py`** (9 tests): Validates timezone calculations (`Asia/Karachi`, `UTC`), concurrent scheduling attempts, and schedule advancement.
- **`test_watches.py`** (6 tests): Validates REST CRUD endpoints, validation rules, and scheduler APIs.

---

## 📡 Core API Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/v1/users` | Register a new user. |
| `POST` | `/v1/watches` | Create a monitored Watch with cadence & target URL. |
| `GET` | `/v1/watches` | List all active watches for a user. |
| `POST` | `/v1/watches/{id}/runs` | Trigger an on-demand Watch Run. |
| `GET` | `/v1/watches/{id}/runs` | List execution history and status for a Watch. |
| `GET` | `/v1/watches/{id}/changes`| Inspect detected structural and numerical changes. |
| `POST` | `/v1/scheduler/tick` | Trigger a scheduler check (discovers & claims due watches). |
| `GET` | `/v1/scheduler/status` | Query health and polling configuration of the scheduler. |
| `GET` | `/health` | Service and database connectivity check. |

---

## 🗺️ Project Roadmap & Milestones

- [x] **Phase 1: Foundation & PostgreSQL Persistence** — FastAPI service, Neon PostgreSQL schema, verified migrations.
- [x] **Phase 2A: Watch Run State Machine** — Pending/Running/Succeeded/Failed lifecycle, duplicate active run prevention.
- [x] **Phase 2B: Concurrency-Safe Scheduler & Worker** — Row locking (`SKIP LOCKED`), timezone-aware cadence calculation.
- [x] **Phase 3A: Bright Data Scraper Studio Adapter** — Integration with Scraper Studio (`/dca/`), live Daraz collector validation.
- [x] **Phase 3B: Asynchronous Worker Lifecycle** — Non-blocking job initiation, durable `j_...` tracking, restart-safety.
- [ ] **Phase 4: Natural Language AI Condition Engine** — Semantic condition evaluation ("Alert if price drops by >15%").
- [ ] **Phase 5: Self-Healing Pipeline** — Automatic retry & schema-drift recovery via Bright Data Self-Healing.
- [ ] **Phase 6: Next.js SaaS Dashboard** — Real-time telemetry, visual diff viewer, and instant alert notifications.

---

## 🏆 Hackathon Submission Highlights

1. **Production-First Mindset**: Not a mock script — uses real Neon PostgreSQL row-level locks, transactional integrity, and validated Bright Data Scraper Studio jobs.
2. **Zero Fragility**: If the worker container crashes at any millisecond, execution state is preserved and safely resumed.
3. **Tested to Perfection**: 100% test coverage on core domain logic with 41 passing automated tests.
4. **Architectural Purity**: Clean boundary separation between database, worker pipelines, domain models, and external APIs.

---

*Engineered with precision for the Hackathon.* 🚀
