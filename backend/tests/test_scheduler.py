import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Schedule, Snapshot, Watch, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import MockRunExecutor
from app.services.scheduler import SchedulerService, calculate_next_due_at
from app.services.worker import WorkerService


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


def make_scheduled_watch(db, next_due_at: datetime, cadence="daily", timezone_name="UTC", status="active"):
    repository = WatchRepository(db)
    user = repository.create_user(UserCreate(email=f"sched-{uuid.uuid4()}@example.com"))
    watch = repository.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/item",
                "title": "Scheduled Item",
                "instruction": "Alert when price is below 2500",
                "monitoring_spec": {"field": "price", "value": 2500},
                "status": status,
                "schedule": {
                    "cadence": cadence,
                    "timezone": timezone_name,
                    "next_due_at": next_due_at.isoformat(),
                },
            }
        )
    )
    return user, watch


def test_timezone_aware_cadence_advancement():
    # Test hourly, daily, weekly, and custom calculation
    base_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)

    next_hourly = calculate_next_due_at(base_time, "hourly", "UTC", now=base_time)
    assert next_hourly == datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    next_daily = calculate_next_due_at(base_time, "daily", "Asia/Karachi", now=base_time)
    assert next_daily == datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)

    next_weekly = calculate_next_due_at(base_time, "weekly", "UTC", now=base_time)
    assert next_weekly == datetime(2026, 8, 25, 9, 0, tzinfo=timezone.utc)

    next_custom = calculate_next_due_at(base_time, "custom", "UTC", now=base_time, custom_minutes=15)
    assert next_custom == datetime(2026, 8, 18, 9, 15, tzinfo=timezone.utc)


def as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def test_due_watch_is_discovered_and_creates_exactly_one_run(db):
    """Requirements A & C: A due watch is discovered and creates exactly one run."""
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    due_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=due_time)

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    executed_runs = scheduler.tick(now=now)

    assert len(executed_runs) == 1
    run = executed_runs[0]
    assert run.watch_id == watch.id
    assert run.status == "succeeded"
    assert as_utc(run.scheduled_for) == due_time

    # Verify Snapshot was created
    snapshot = db.scalar(select(Snapshot).where(Snapshot.run_id == run.id))
    assert snapshot is not None
    assert snapshot.watch_id == watch.id


def test_future_watch_is_not_executed(db):
    """Requirement B: A future watch is not executed."""
    now = datetime(2026, 8, 18, 8, 0, tzinfo=timezone.utc)
    future_time = datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=future_time)

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    executed_runs = scheduler.tick(now=now)

    assert executed_runs == []
    runs_in_db = db.scalars(select(WatchRun).where(WatchRun.watch_id == watch.id)).all()
    assert runs_in_db == []


def test_two_concurrent_scheduler_attempts_cannot_create_duplicate_active_runs(db):
    """Requirement D: Two concurrent scheduler attempts cannot create duplicate active runs."""
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    due_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=due_time)

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    # First scheduler claims and creates pending run
    created_runs = scheduler.claim_and_create_runs(now=now)
    assert len(created_runs) == 1
    assert created_runs[0].status == "pending"

    # Second concurrent tick attempt while run is still pending/running
    second_created_runs = scheduler.claim_and_create_runs(now=now)
    assert second_created_runs == []

    # Total runs for this watch in DB should strictly be 1
    runs = db.scalars(select(WatchRun).where(WatchRun.watch_id == watch.id)).all()
    assert len(runs) == 1


def test_next_due_at_advances_after_scheduled_execution(db):
    """Requirement E: next_due_at advances after a scheduled execution."""
    start_due = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 18, 9, 5, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=start_due, cadence="daily")

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    scheduler.tick(now=now)

    schedule = db.scalar(select(Schedule).where(Schedule.watch_id == watch.id))
    assert schedule is not None
    assert as_utc(schedule.next_due_at) > now
    assert as_utc(schedule.next_due_at) == datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)


def test_failed_run_does_not_permanently_block_watch(db):
    """Requirement F: A failed Run does not permanently block the Watch."""
    t1 = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=t1, cadence="daily")

    # Tick 1 with failure
    failing_executor = MockRunExecutor(db)
    original_execute = failing_executor.execute
    failing_executor.execute = lambda run, **kw: original_execute(run, fail=True)

    scheduler = SchedulerService(db, executor=failing_executor)
    executed_1 = scheduler.tick(now=t1 + timedelta(minutes=1))
    assert len(executed_1) == 1
    assert executed_1[0].status == "failed"

    # Verify schedule advanced to next day
    schedule = db.scalar(select(Schedule).where(Schedule.watch_id == watch.id))
    assert as_utc(schedule.next_due_at) == datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)

    # Tick 2 on the next day with normal executor succeeds
    normal_scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    t2 = datetime(2026, 8, 19, 9, 5, tzinfo=timezone.utc)
    executed_2 = normal_scheduler.tick(now=t2)
    assert len(executed_2) == 1
    assert executed_2[0].status == "succeeded"


def test_restarting_scheduler_does_not_lose_due_watches(db):
    """Requirement G: Restarting the scheduler does not lose due Watches."""
    due_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=due_time)

    # Process 1 creates scheduler instance and simulates stopping
    scheduler_instance_1 = SchedulerService(db, executor=MockRunExecutor(db))
    del scheduler_instance_1

    # Process 2 starts later and queries PostgreSQL/database
    scheduler_instance_2 = SchedulerService(db, executor=MockRunExecutor(db))
    executed = scheduler_instance_2.tick(now=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))

    assert len(executed) == 1
    assert executed[0].watch_id == watch.id
    assert executed[0].status == "succeeded"


def test_multiple_independent_watches_scheduled_independently(db):
    """Requirement H: Multiple independent Watches can be scheduled independently."""
    t_due = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    t_future = datetime(2026, 8, 18, 15, 0, tzinfo=timezone.utc)
    now = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)

    _, watch_due_1 = make_scheduled_watch(db, next_due_at=t_due, cadence="hourly")
    _, watch_due_2 = make_scheduled_watch(db, next_due_at=t_due, cadence="daily")
    _, watch_future = make_scheduled_watch(db, next_due_at=t_future, cadence="daily")

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    executed = scheduler.tick(now=now)

    executed_watch_ids = {r.watch_id for r in executed}
    assert executed_watch_ids == {watch_due_1.id, watch_due_2.id}
    assert watch_future.id not in executed_watch_ids


def test_worker_service_idempotency_and_pending_processing(db):
    """Test WorkerService handles pending runs and prevents duplicate snapshot processing."""
    due_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    _, watch = make_scheduled_watch(db, next_due_at=due_time)

    scheduler = SchedulerService(db, executor=MockRunExecutor(db))
    created_runs = scheduler.claim_and_create_runs(now=due_time)
    assert len(created_runs) == 1
    run_id = created_runs[0].id
    assert created_runs[0].status == "pending"

    worker = WorkerService(db, executor=MockRunExecutor(db))
    executed_run = worker.process_run(run_id)
    assert executed_run.status == "succeeded"

    # Re-processing the already completed run is idempotent and does not create duplicate snapshots
    re_processed = worker.process_run(run_id)
    assert re_processed.status == "succeeded"
    assert len(db.scalars(select(Snapshot).where(Snapshot.run_id == run_id)).all()) == 1

