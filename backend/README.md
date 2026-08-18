# Web Radar backend

Phase 1 provides a FastAPI service for persistent Watch CRUD. Neon PostgreSQL is the production system of record. No scheduler, AI workflow, frontend, or live Bright Data request is included yet.

## Local development

Create and activate a Python 3.11+ virtual environment, then install the service and test dependencies:

```powershell
cd backend
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
```

Set `DATABASE_URL` to a PostgreSQL database (Neon is supported), then apply every migration in filename order from the repository root:

```powershell
./database/migrate.ps1
```

The migration tool tracks applied files in `schema_migrations`; it is safe to rerun and refuses to continue if an already-applied migration has changed.

Run the API with `uvicorn app.main:app --reload` and run tests with `pytest` from `backend/`. Tests use an isolated SQLite database and do not contact Bright Data or Neon. To enable the opt-in Neon integration test, set `RUN_POSTGRES_INTEGRATION=1` and a non-production `DATABASE_URL`, then run `pytest -m postgres`.
