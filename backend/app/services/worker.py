import logging
from typing import Any
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import WatchRun
from app.services.runs import BrightDataRunExecutor, MockRunExecutor

logger = logging.getLogger(__name__)


class WorkerService:
    """Consumes pending Runs and polls running Bright Data jobs asynchronously."""

    def __init__(self, db: Session, executor: Any | None = None):
        self.db = db
        if executor is not None:
            self.executor = executor
        else:
            from app.config import get_settings
            settings = get_settings()
            if settings.bright_data_api_key:
                self.executor = BrightDataRunExecutor(db)
            else:
                self.executor = MockRunExecutor(db)

    def process_run(self, run_id: str) -> WatchRun | None:
        """Process a single run: initiate if pending, poll/finalize if running."""
        run = self.db.get(WatchRun, run_id)
        if run is None:
            return None
        if run.status in {"succeeded", "failed"}:
            # Idempotency guard: never re-execute terminal runs
            return run
        return self.executor.execute(run)

    def process_pending_runs(self, limit: int = 50) -> list[WatchRun]:
        """Claim and initiate pending runs without blocking."""
        stmt = (
            select(WatchRun)
            .where(WatchRun.status == "pending")
            .order_by(WatchRun.scheduled_for.asc())
            .limit(limit)
        )
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            stmt = stmt.with_for_update(skip_locked=True)

        pending_runs = list(self.db.scalars(stmt).all())
        results: list[WatchRun] = []
        for run in pending_runs:
            try:
                executed = self.executor.execute(run)
                results.append(executed)
            except Exception as exc:
                logger.error("Failed to initiate pending run %s: %s", run.id, exc)
        return results

    def process_running_runs(self, limit: int = 50) -> list[WatchRun]:
        """Poll and finalize active running jobs with stored Bright Data identifiers."""
        stmt = (
            select(WatchRun)
            .where(
                WatchRun.status == "running",
                WatchRun.bright_data_collection_id.is_not(None),
            )
            .order_by(WatchRun.started_at.asc())
            .limit(limit)
        )
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            stmt = stmt.with_for_update(skip_locked=True)

        running_runs = list(self.db.scalars(stmt).all())
        results: list[WatchRun] = []
        for run in running_runs:
            try:
                executed = self.executor.execute(run)
                results.append(executed)
            except Exception as exc:
                logger.error("Failed to poll/finalize running run %s: %s", run.id, exc)
        return results

    def tick(self, limit: int = 50) -> dict[str, list[WatchRun]]:
        """Worker tick cycle: polls in-flight jobs, then initiates pending runs."""
        polled = self.process_running_runs(limit=limit)
        initiated = self.process_pending_runs(limit=limit)
        return {
            "running": polled,
            "pending": initiated,
        }
