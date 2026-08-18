"""Opt-in integration coverage for a disposable Neon/PostgreSQL database."""

import os
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models import Change, Snapshot, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import (
    ActiveRunExistsError,
    MockRunExecutor,
    RunCreationService,
)

pytestmark = pytest.mark.postgres


@pytest.fixture()
def postgres_db():
    if os.getenv("RUN_POSTGRES_INTEGRATION") != "1":
        pytest.skip("set RUN_POSTGRES_INTEGRATION=1 to enable PostgreSQL integration tests")
    database_url = os.environ.get("DATABASE_URL") or get_settings().database_url
    if not database_url or "replace-me" in database_url:
        pytest.fail("RUN_POSTGRES_INTEGRATION requires a non-placeholder DATABASE_URL")
    if database_url.startswith("postgresql://"):
        database_url = database_url.replace("postgresql://", "postgresql+psycopg://", 1)

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    session = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        engine.dispose()


def make_postgres_watch(db, status="active"):
    repository = WatchRepository(db)
    user = repository.create_user(UserCreate(email=f"pg-{uuid.uuid4()}@example.com"))
    watch = repository.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/product",
                "title": "PostgreSQL test product",
                "instruction": "Alert when price is below PKR 2500.",
                "monitoring_spec": {"field": "price", "operator": "lt", "value": 2500},
                "status": status,
                "schedule": {
                    "cadence": "daily",
                    "timezone": "Asia/Karachi",
                    "next_due_at": "2026-08-18T09:00:00+05:00",
                },
            }
        )
    )
    return user, watch


def test_watch_run_full_lifecycle_and_changes_against_postgres(postgres_db):
    user, watch = make_postgres_watch(postgres_db)
    creation_service = RunCreationService(postgres_db)
    executor = MockRunExecutor(postgres_db)

    # 1 & 2. Watch Run creation in pending state
    t1 = datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    first_run = creation_service.create(watch.id, scheduled_for=t1)
    assert first_run.status == "pending"
    assert first_run.watch_id == watch.id

    # 3 & 4. Lifecycle: pending -> running -> succeeded and Snapshot persistence
    first_run = executor.execute(first_run, payload={"price": 3000, "currency": "PKR"})
    assert first_run.status == "succeeded"
    assert first_run.started_at is not None
    assert first_run.finished_at is not None

    snapshot_1 = postgres_db.scalar(select(Snapshot).where(Snapshot.run_id == first_run.id))
    assert snapshot_1 is not None
    assert snapshot_1.watch_id == watch.id
    assert snapshot_1.payload == {"price": 3000, "currency": "PKR"}
    assert snapshot_1.metadata_["source"] == "mock"

    # First run produces no changes
    assert postgres_db.scalars(select(Change).where(Change.run_id == first_run.id)).all() == []

    # 5. Second run with changed data produces persisted Change records
    t2 = datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc)
    second_run = creation_service.create(watch.id, scheduled_for=t2)
    second_run = executor.execute(
        second_run,
        payload={"price": 2400, "currency": "PKR", "availability": "in_stock"},
    )
    assert second_run.status == "succeeded"

    changes = postgres_db.scalars(select(Change).where(Change.run_id == second_run.id)).all()
    change_types = {c.change_type for c in changes}
    assert "value_changed" in change_types
    assert "field_added" in change_types

    # 8. Clean up and verify cascade delete behavior
    WatchRepository(postgres_db).delete(watch)
    assert postgres_db.scalar(select(WatchRun).where(WatchRun.id == first_run.id)) is None
    assert postgres_db.scalar(select(Snapshot).where(Snapshot.id == snapshot_1.id)) is None
    assert postgres_db.scalars(select(Change).where(Change.watch_id == watch.id)).all() == []
    postgres_db.delete(user)
    postgres_db.commit()


def test_failed_run_behavior_against_postgres(postgres_db):
    user, watch = make_postgres_watch(postgres_db)
    creation_service = RunCreationService(postgres_db)
    executor = MockRunExecutor(postgres_db)

    # 6. Failed Run behavior
    run = creation_service.create(watch.id)
    failed_run = executor.execute(run, fail=True)

    assert failed_run.status == "failed"
    assert failed_run.error_code == "mock_execution_failed"
    assert failed_run.error_detail == "mock extraction failed"
    assert failed_run.finished_at is not None

    # Verify no snapshot was created
    assert postgres_db.scalar(select(Snapshot).where(Snapshot.run_id == run.id)) is None

    # Cleanup
    WatchRepository(postgres_db).delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()


def test_duplicate_active_run_protection_against_postgres(postgres_db):
    user, watch = make_postgres_watch(postgres_db)
    creation_service = RunCreationService(postgres_db)

    # 7. Duplicate active run protection enforced in PostgreSQL
    first_run = creation_service.create(watch.id)
    assert first_run.status == "pending"

    with pytest.raises(ActiveRunExistsError):
        creation_service.create(watch.id)

    # Cleanup
    WatchRepository(postgres_db).delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()


def test_scheduler_and_worker_lifecycle_against_postgres(postgres_db):
    from app.models import Schedule
    from app.services.runs import MockRunExecutor
    from app.services.scheduler import SchedulerService

    due_time = datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc)
    user, watch = make_postgres_watch(postgres_db)
    # Set schedule next_due_at to due_time
    schedule = postgres_db.scalar(select(Schedule).where(Schedule.watch_id == watch.id))
    schedule.next_due_at = due_time
    postgres_db.commit()

    now = datetime(2026, 8, 18, 9, 5, tzinfo=timezone.utc)
    scheduler = SchedulerService(postgres_db, executor=MockRunExecutor(postgres_db))

    # Tick 1: Discovers due watch, advances next_due_at, creates and executes run
    executed_runs = [r for r in scheduler.tick(now=now) if r.watch_id == watch.id]
    assert len(executed_runs) == 1
    run = executed_runs[0]
    assert run.status == "succeeded"
    assert run.watch_id == watch.id

    # Verify next_due_at was advanced in PostgreSQL
    postgres_db.refresh(schedule)
    assert schedule.next_due_at == datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)

    # Tick 2 at same time: Future schedule is not re-executed
    second_tick_runs = [r for r in scheduler.tick(now=now) if r.watch_id == watch.id]
    assert second_tick_runs == []


    # Cleanup
    WatchRepository(postgres_db).delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()


@pytest.mark.bright_data
def test_real_bright_data_worker_lifecycle_against_postgres(postgres_db):
    """Real end-to-end integration test: Neon DB + real Bright Data Scraper Studio execution."""
    import time
    from app.config import get_settings
    from app.integrations.bright_data import HttpBrightDataAdapter
    from app.models import Snapshot, WatchRun
    from app.services.runs import BrightDataRunExecutor, RunCreationService
    from app.services.worker import WorkerService

    settings = get_settings()
    api_key = settings.bright_data_api_key or os.getenv("BRIGHTDATA_API_KEY") or os.getenv("BRIGHT_DATA_API_KEY")
    collector_id = settings.bright_data_collector_id or os.getenv("BRIGHTDATA_COLLECTOR_ID") or os.getenv("BRIGHT_DATA_COLLECTOR_ID")

    if not api_key or not collector_id:
        pytest.skip("BRIGHTDATA_API_KEY and BRIGHTDATA_COLLECTOR_ID required for live test")

    repo = WatchRepository(postgres_db)
    user = repo.create_user(UserCreate(email=f"bd-pg-{uuid.uuid4()}@example.com"))
    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://www.daraz.pk/products/m10-tws-wireless-bluetooth-earbuds-touch-control-waterproof-headsets-with-microphone-i435345719.html",
                "title": "Live Daraz Earbuds",
                "instruction": "Track live price from Scraper Studio",
                "monitoring_spec": {"field": "price", "threshold": 2000, "scraper_id": collector_id},
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )

    creation_service = RunCreationService(postgres_db)
    run = creation_service.create(watch.id)
    assert run.status == "pending"

    adapter = HttpBrightDataAdapter(api_key=api_key, base_url=settings.bright_data_base_url)
    executor = BrightDataRunExecutor(postgres_db, adapter=adapter, default_collector_id=collector_id)
    worker = WorkerService(postgres_db, executor=executor)

    # 1. Trigger collection and persist external ID to Neon
    initiated_run = worker.process_run(run.id)
    assert initiated_run is not None
    assert initiated_run.status == "running"
    assert initiated_run.bright_data_collection_id is not None
    assert initiated_run.bright_data_collection_id.startswith("j_")

    # Verify persisted in Neon PostgreSQL
    postgres_db.refresh(run)
    assert run.bright_data_collection_id == initiated_run.bright_data_collection_id
    assert run.status == "running"

    # 2. Asynchronous polling loop via worker tick
    max_wait = 180
    start = time.time()
    final_run = None
    while (time.time() - start) < max_wait:
        # Worker tick polls running runs from Neon and queries Bright Data
        tick_res = worker.tick()
        postgres_db.refresh(run)
        if run.status in {"succeeded", "failed"}:
            final_run = run
            break
        time.sleep(4.0)

    assert final_run is not None, f"Run {run.id} did not finalize within {max_wait}s"
    if final_run.status == "succeeded":
        # 3a. Verify Snapshot persistence in Neon
        snapshot = postgres_db.scalar(select(Snapshot).where(Snapshot.run_id == run.id))
        assert snapshot is not None
        assert snapshot.watch_id == watch.id
        assert "url" in snapshot.payload
        assert "title" in snapshot.payload
        assert snapshot.metadata_["source"] == "bright_data"
        assert snapshot.metadata_["collection_id"] == run.bright_data_collection_id
    else:
        # 3b. If target page layout caused extraction schema failure, verify self-healing repair in Neon
        assert final_run.status == "failed"
        assert final_run.error_code == "extraction_schema_failure"
        from app.models import ScraperRepair
        repair = postgres_db.scalar(select(ScraperRepair).where(ScraperRepair.run_id == run.id))
        assert repair is not None
        assert repair.watch_id == watch.id
        assert repair.collector_id == collector_id
        assert "price" in repair.missing_fields

    # 4. Idempotency check: Reprocessing finalized run is a no-op
    reprocessed = worker.process_run(run.id)
    assert reprocessed.status == final_run.status


    # Cleanup
    repo.delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()


def test_semantic_alerts_and_crossing_against_postgres(postgres_db):
    """Verify deterministic semantic rule evaluation, alert creation and crossing logic on Neon PostgreSQL."""
    from app.models import Alert
    repo = WatchRepository(postgres_db)
    user = repo.create_user(UserCreate(email=f"alerts-pg-{uuid.uuid4()}@example.com"))
    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/product",
                "title": "Postgres Alert Product",
                "instruction": "Alert when price < 2500",
                "monitoring_spec": {
                    "field": "price",
                    "currency": "PKR",
                    "rules": [{"type": "price_below", "field": "price", "value": 2500, "currency": "PKR"}],
                },
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )

    creation = RunCreationService(postgres_db)
    executor = MockRunExecutor(postgres_db)

    # Run 1: baseline price 3000
    run1 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc))
    executor.execute(run1, payload={"url": watch.url, "title": watch.title, "price": 3000, "currency": "PKR"})
    alerts1 = postgres_db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all()
    assert len(alerts1) == 0

    # Run 2: price drops to 2399 (crosses below 2500)
    run2 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    executor.execute(run2, payload={"url": watch.url, "title": watch.title, "price": 2399, "currency": "PKR"})

    alerts2 = list(postgres_db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all())
    event_types2 = {a.event_type for a in alerts2}
    assert "price_threshold_crossed" in event_types2
    assert "price_decreased" in event_types2

    # Verify Alert persisted fields in Neon
    crossed_alert = next(a for a in alerts2 if a.event_type == "price_threshold_crossed")
    assert crossed_alert.run_id == run2.id
    assert crossed_alert.details["previous_value"] == 3000
    assert crossed_alert.details["current_value"] == 2399
    assert crossed_alert.details["rule_value"] == 2500
    assert crossed_alert.idempotency_key is not None

    # Run 3: price drops further to 2299 (still below 2500)
    run3 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc))
    executor.execute(run3, payload={"url": watch.url, "title": watch.title, "price": 2299, "currency": "PKR"})

    alerts3 = list(postgres_db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all())
    run3_alerts = [a for a in alerts3 if a.run_id == run3.id]
    run3_types = {a.event_type for a in run3_alerts}
    assert "price_decreased" in run3_types
    assert "price_threshold_crossed" not in run3_types  # Anti-spam: no duplicate crossing

    # Cleanup
    repo.delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()


def test_self_healing_and_repairs_against_postgres(postgres_db):
    """Verify schema failure detection, ScraperRepair creation and persistence against Neon PostgreSQL."""
    from app.integrations.bright_data import MockBrightDataAdapter
    from app.models import ScraperRepair
    from app.services.runs import BrightDataRunExecutor

    repo = WatchRepository(postgres_db)
    user = repo.create_user(UserCreate(email=f"heal-pg-{uuid.uuid4()}@example.com"))
    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/product/heal",
                "title": "Neon Heal Product",
                "instruction": "Monitor price",
                "monitoring_spec": {
                    "collector_id": "c_neon_custom_999",
                    "field": "price",
                    "currency": "PKR",
                },
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )

    creation = RunCreationService(postgres_db)
    run = creation.create(watch.id)

    # Corrupted payload with price = None (schema failure)
    corrupted_data = [{"url": watch.url, "title": watch.title, "price": None, "currency": "PKR"}]
    adapter = MockBrightDataAdapter(preset_data=corrupted_data, preset_status="ready")
    executor = BrightDataRunExecutor(postgres_db, adapter=adapter, default_collector_id="c_neon_custom_999")

    # Execute run -> initiates, detects schema failure, creates ScraperRepair in Neon
    executed_run = executor.execute(run)
    assert executed_run.status == "failed"
    assert executed_run.error_code == "extraction_schema_failure"

    # Verify ScraperRepair record exists in Neon PostgreSQL
    repair = postgres_db.scalar(select(ScraperRepair).where(ScraperRepair.run_id == run.id))
    assert repair is not None
    assert repair.watch_id == watch.id
    assert repair.collector_id == "c_neon_custom_999"
    assert repair.status == "in_progress"
    assert "price" in repair.missing_fields
    assert repair.repair_prompt is not None

    # Idempotency: re-running does not duplicate repairs in Neon
    executor.execute(run)
    repairs_count = len(postgres_db.scalars(select(ScraperRepair).where(ScraperRepair.run_id == run.id)).all())
    assert repairs_count == 1

    # Cleanup
    repo.delete(watch)
    postgres_db.delete(user)
    postgres_db.commit()





