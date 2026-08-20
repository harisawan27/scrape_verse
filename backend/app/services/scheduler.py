import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session_factory
from app.models import Schedule, Watch, WatchRun, utc_now
from app.services.runs import (
    ActiveRunExistsError,
    BrightDataRunExecutor,
    MockRunExecutor,
    RunCreationService,
)


logger = logging.getLogger(__name__)


def calculate_next_due_at(
    current_due: datetime,
    cadence: str,
    tz_name: str = "UTC",
    now: datetime | None = None,
    custom_minutes: int | None = None,
) -> datetime:
    """Calculate the next scheduled due datetime, strictly preserving IANA timezone alignment."""
    try:
        tz = ZoneInfo(tz_name)
    except Exception:
        tz = timezone.utc

    if current_due.tzinfo is None:
        current_due = current_due.replace(tzinfo=timezone.utc)

    local_due = current_due.astimezone(tz)
    reference_now = (now or utc_now()).astimezone(tz)

    if cadence == "hourly":
        delta = timedelta(hours=1)
    elif cadence == "daily":
        delta = timedelta(days=1)
    elif cadence == "weekly":
        delta = timedelta(weeks=1)
    elif cadence == "custom":
        delta = timedelta(minutes=custom_minutes or 60)
    else:
        delta = timedelta(days=1)

    next_due = local_due + delta

    # If next_due is still in the past compared to reference_now (e.g. process restart after downtime),
    # advance in uniform cadence steps to catch up while preserving time-of-day alignment.
    if next_due <= reference_now:
        diff_seconds = (reference_now - next_due).total_seconds()
        step_seconds = delta.total_seconds()
        if step_seconds > 0:
            steps = int(diff_seconds // step_seconds) + 1
            next_due = next_due + (delta * steps)

    return next_due.astimezone(timezone.utc)


class SchedulerService:
    """Discovers due Watches in PostgreSQL, claims them safely, and enqueues Runs."""

    def __init__(
        self,
        db: Session,
        executor: Any | None = None,
        run_creator: RunCreationService | None = None,
    ):
        self.db = db
        if executor is not None:
            self.executor = executor
        else:
            from app.config import get_settings
            from app.services.runs import BrightDataRunExecutor, MockRunExecutor

            settings = get_settings()
            if settings.bright_data_api_key:
                self.executor = BrightDataRunExecutor(db)
            else:
                self.executor = MockRunExecutor(db)
        self.run_creator = run_creator or RunCreationService(db)

    def claim_due_schedules(self, now: datetime | None = None, limit: int = 100) -> list[Schedule]:
        """Query active watches whose next_due_at <= now, locking rows with SKIP LOCKED in PostgreSQL."""
        query_time = now or utc_now()
        stmt = (
            select(Schedule)
            .join(Watch, Schedule.watch_id == Watch.id)
            .where(
                Schedule.enabled.is_(True),
                Watch.status == "active",
                Schedule.next_due_at <= query_time,
            )
            .order_by(Schedule.next_due_at.asc())
            .limit(limit)
        )
        if self.db.bind and self.db.bind.dialect.name != "sqlite":
            stmt = stmt.with_for_update(of=Schedule, skip_locked=True)

        return list(self.db.scalars(stmt).all())

    def claim_and_create_runs(self, now: datetime | None = None, limit: int = 100) -> list[WatchRun]:
        """Claim due schedules, advance next_due_at, and create pending WatchRuns."""
        due_schedules = self.claim_due_schedules(now=now, limit=limit)
        created_runs: list[WatchRun] = []

        for schedule in due_schedules:
            watch = self.db.get(Watch, schedule.watch_id)
            if watch is None or watch.status != "active":
                continue

            scheduled_slot = schedule.next_due_at
            schedule.next_due_at = calculate_next_due_at(
                current_due=scheduled_slot,
                cadence=schedule.cadence,
                tz_name=schedule.timezone,
                now=now,
            )
            self.db.add(schedule)

            try:
                run = self.run_creator.create(watch.id, scheduled_for=scheduled_slot)
                created_runs.append(run)
            except ActiveRunExistsError:
                self.db.commit()
                continue
            except Exception as exc:
                self.db.rollback()
                logger.warning("Failed to create scheduled run for watch %s: %s", watch.id, exc)
                continue

        return created_runs

    def tick(self, now: datetime | None = None) -> list[WatchRun]:
        """Claim all due runs, initiate pending runs, and poll active running jobs."""
        runs = self.claim_and_create_runs(now)
        executed_runs: list[WatchRun] = []
        for run in runs:
            executed = self.executor.execute(run)
            executed_runs.append(executed)

        # Poll existing running runs with Bright Data collection IDs only if using BrightDataRunExecutor
        if isinstance(self.executor, BrightDataRunExecutor):
            stmt = select(WatchRun).where(
                WatchRun.status == "running",
                WatchRun.bright_data_collection_id.is_not(None),
            )
            if executed_runs:
                stmt = stmt.where(WatchRun.id.not_in([r.id for r in executed_runs]))
            if self.db.bind and self.db.bind.dialect.name != "sqlite":
                stmt = stmt.with_for_update(skip_locked=True)

            running_runs = list(self.db.scalars(stmt).all())
            for run in running_runs:
                try:
                    polled = self.executor.execute(run)
                    executed_runs.append(polled)
                except Exception as exc:
                    logger.error("Failed to poll running run %s: %s", run.id, exc)

        return executed_runs



class AsyncSchedulerRunner:
    """Development background loop with configurable polling and clean shutdown."""

    def __init__(self, poll_interval_seconds: float = 5.0):
        self.poll_interval_seconds = poll_interval_seconds
        self._task: asyncio.Task[None] | None = None
        self._running: bool = False

    @property
    def is_running(self) -> bool:
        return self._running

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Scheduler runner started (interval=%.1fs)", self.poll_interval_seconds)


    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler runner stopped")

    async def _loop(self) -> None:
        session_factory = get_session_factory()
        while self._running:
            try:
                with session_factory() as db:
                    scheduler = SchedulerService(db)
                    executed = scheduler.tick()
                    if executed:
                        logger.info("Scheduler tick executed %d run(s)", len(executed))
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.exception("Unexpected error in scheduler tick: %s", exc)

            try:
                await asyncio.sleep(self.poll_interval_seconds)
            except asyncio.CancelledError:
                break
