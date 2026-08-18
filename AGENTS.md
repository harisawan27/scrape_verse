# Repository Guidelines

## Project Status and Decision Gate

Web Radar is a hackathon project for persistent, server-side web monitoring. The application is **not yet approved for implementation**. Before adding product code, submit and obtain review of the architecture, PostgreSQL schema, API design, folder layout, scheduling approach, Bright Data boundaries, self-healing plan, frontend state model, and testing strategy. Record decisions and open questions in the project documentation; do not silently choose a provider, data model, or background-job mechanism.

## Intended Structure

Organize the repository by deployable boundary:

- `frontend/` — Next.js UI, routes, components, and client state.
- `backend/` — Python API, domain services, workers, and integrations suitable for Hugging Face Spaces.
- `database/` — Neon PostgreSQL migrations, seed data, and schema notes.
- `docs/` — architecture decisions, API contracts, and operational runbooks.
- `tests/` — cross-service integration and end-to-end tests; colocate focused unit tests with their modules when useful.

Keep domain language consistent: `User`, `Watch`, `Scraper`, `Schedule`, `Run`, `Snapshot`, `Change`, `Alert`, and `Notification`.

## Engineering Principles

The backend and database are the source of truth. The browser must never schedule monitoring or own monitoring state. A Watch, its runs, snapshots, changes, alerts, and notifications must persist after the browser closes. Use normal code for deterministic work (scheduling, comparisons, validation, and condition evaluation); reserve LLM calls for genuinely semantic interpretation or natural-language Watch edits.

## Bright Data Integration

Use Bright Data Scraper Studio custom scrapers behind a backend integration boundary. Convert scraper output into validated structured snapshots before persistence. Keep Bright Data request/response details out of UI and domain models. For supported failures, route retries and recovery through Bright Data Self-Healing, then store the outcome in the Run history.

## Development, Testing, and Reviews

Do not add dependencies until a reviewed design demonstrates the need. When tooling is introduced, document exact local commands here and in the relevant package README. Test the full lifecycle: scheduled run, snapshot persistence, semantic change detection, condition evaluation, alert creation, retry/self-healing, and history visibility. Pull requests should state the design decision, affected domain concepts, migration impact, tests run, and UI screenshots where applicable.
