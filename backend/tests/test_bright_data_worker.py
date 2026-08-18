import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.integrations.bright_data import MockBrightDataAdapter
from app.models import Base, Change, Snapshot, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import BrightDataRunExecutor, RunCreationService
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


def create_test_watch(db, *, scraper_id: str = "c_msz0zrtw29tjzhzakl", url: str = "https://www.daraz.pk/products/item-1"):
    repo = WatchRepository(db)
    user = repo.create_user(UserCreate(email=f"worker-{uuid.uuid4()}@example.com"))
    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": url,
                "title": "Test Daraz Product",
                "instruction": "Alert when price < 2000",
                "monitoring_spec": {"field": "price", "threshold": 2000, "scraper_id": scraper_id},
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )
    return user, watch



def test_pending_run_triggers_bright_data_and_persists_job_id(db):
    """1. Pending Run triggers exactly one Bright Data job and persists j_... ID."""
    _, watch = create_test_watch(db)
    run = RunCreationService(db).create(watch.id)
    assert run.status == "pending"
    assert run.bright_data_collection_id is None

    mock_adapter = MockBrightDataAdapter(
        preset_collection_id="j_bd_test_9988",
        preset_status="running",
    )
    executor = BrightDataRunExecutor(db, adapter=mock_adapter, default_collector_id="c_msz0zrtw29tjzhzakl")
    worker = WorkerService(db, executor=executor)

    # Worker initiates pending run
    processed = worker.process_run(run.id)
    assert processed is not None
    assert processed.status == "running"
    assert processed.bright_data_collection_id == "j_bd_test_9988"
    assert len(mock_adapter.triggered_calls) == 1
    assert mock_adapter.triggered_calls[0]["collector_id"] == "c_msz0zrtw29tjzhzakl"
    assert mock_adapter.triggered_calls[0]["inputs"] == [{"url": watch.url}]


def test_running_non_ready_run_stays_running(db):
    """2. Running Run that is still building/processing stays in running state."""
    _, watch = create_test_watch(db)
    run = RunCreationService(db).create(watch.id)

    mock_adapter = MockBrightDataAdapter(
        preset_collection_id="j_bd_test_5544",
        preset_status="running",
    )
    executor = BrightDataRunExecutor(db, adapter=mock_adapter)
    worker = WorkerService(db, executor=executor)

    # 1. Initiate
    worker.process_run(run.id)
    assert run.status == "running"

    # 2. Re-poll while still running
    repolled = worker.process_run(run.id)
    assert repolled.status == "running"
    assert repolled.bright_data_collection_id == "j_bd_test_5544"
    # Verify no second trigger call occurred
    assert len(mock_adapter.triggered_calls) == 1


def test_worker_restart_resumes_from_stored_external_id_without_retriggering(db):
    """3. Backend restart recovers from DB and polls stored external ID without retriggering."""
    _, watch = create_test_watch(db)
    run = RunCreationService(db).create(watch.id)
    run.status = "running"
    run.bright_data_collection_id = "j_persisted_before_crash_123"
    db.commit()

    # Simulate fresh worker instance after restart
    mock_adapter = MockBrightDataAdapter(
        preset_collection_id="j_persisted_before_crash_123",
        preset_status="running",
    )
    new_executor = BrightDataRunExecutor(db, adapter=mock_adapter)
    new_worker = WorkerService(db, executor=new_executor)

    # Worker tick discovers running runs and polls them
    tick_result = new_worker.tick()
    assert len(tick_result["running"]) == 1
    polled_run = tick_result["running"][0]
    assert polled_run.id == run.id
    assert polled_run.status == "running"
    # Critical: ZERO trigger calls made
    assert len(mock_adapter.triggered_calls) == 0


def test_ready_result_creates_snapshot_and_changes(db):
    """4. Ready result downloads data, creates Snapshot, calculates Changes, and succeeds."""
    _, watch = create_test_watch(db)
    run1 = RunCreationService(db).create(watch.id, scheduled_for=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc))

    # Run 1: initial price 2499
    data1 = [
        {
            "url": watch.url,
            "title": "Daraz Wireless Earbuds",
            "price": 2499,
            "currency": "PKR",
            "availability": "in_stock",
        }
    ]
    mock_adapter1 = MockBrightDataAdapter(
        preset_collection_id="j_run_1",
        preset_status="ready",
        preset_data=data1,
    )
    worker1 = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=mock_adapter1))
    executed1 = worker1.process_run(run1.id)
    assert executed1.status == "succeeded"

    # Verify Snapshot 1
    s1 = db.scalar(select(Snapshot).where(Snapshot.run_id == run1.id))
    assert s1 is not None
    assert s1.payload["price"] == 2499
    assert s1.payload["title"] == "Daraz Wireless Earbuds"
    # First snapshot has no changes
    changes1 = db.scalars(select(Change).where(Change.run_id == run1.id)).all()
    assert len(changes1) == 0

    # Run 2: price dropped to 1999
    run2 = RunCreationService(db).create(watch.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    data2 = [
        {
            "url": watch.url,
            "title": "Daraz Wireless Earbuds",
            "price": 1999,
            "currency": "PKR",
            "availability": "in_stock",
        }
    ]
    mock_adapter2 = MockBrightDataAdapter(
        preset_collection_id="j_run_2",
        preset_status="ready",
        preset_data=data2,
    )
    worker2 = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=mock_adapter2))
    executed2 = worker2.process_run(run2.id)
    assert executed2.status == "succeeded"

    # Verify Snapshot 2 and Change detection
    s2 = db.scalar(select(Snapshot).where(Snapshot.run_id == run2.id))
    assert s2 is not None
    assert s2.payload["price"] == 1999

    changes2 = list(db.scalars(select(Change).where(Change.run_id == run2.id)).all())
    assert len(changes2) == 1
    assert changes2[0].change_type == "value_changed"
    assert changes2[0].details["old_value"] == 2499
    assert changes2[0].details["new_value"] == 1999
    assert changes2[0].details["path"] == "$.price"




def test_idempotent_duplicate_processing_does_not_duplicate_jobs_or_snapshots(db):
    """5. Processing a completed run is a strict no-op and never creates extra snapshots."""
    _, watch = create_test_watch(db)
    run = RunCreationService(db).create(watch.id)

    mock_adapter = MockBrightDataAdapter(
        preset_collection_id="j_bd_idempotent_77",
        preset_status="ready",
        preset_data=[{"url": watch.url, "title": "Watch Title", "price": 1000}],
    )
    worker = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=mock_adapter))

    # Pass 1: executes and succeeds
    res1 = worker.process_run(run.id)
    assert res1.status == "succeeded"
    snapshots_count = len(db.scalars(select(Snapshot).where(Snapshot.run_id == run.id)).all())
    assert snapshots_count == 1

    # Pass 2: reprocessing is a no-op
    res2 = worker.process_run(run.id)
    assert res2.status == "succeeded"
    assert len(mock_adapter.triggered_calls) == 1
    snapshots_count_after = len(db.scalars(select(Snapshot).where(Snapshot.run_id == run.id)).all())
    assert snapshots_count_after == 1


def test_failed_bright_data_job_marks_run_failed(db):
    """6. Failed Bright Data job sets status='failed' and creates no Snapshot."""
    _, watch = create_test_watch(db)
    run = RunCreationService(db).create(watch.id)

    mock_adapter = MockBrightDataAdapter(
        preset_collection_id="j_failed_job_99",
        preset_status="failed",
    )
    worker = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=mock_adapter))

    executed = worker.process_run(run.id)
    assert executed.status == "failed"
    assert executed.error_code == "bright_data_collection_failed"

    # Confirm NO snapshot is created for failed runs
    snapshot = db.scalar(select(Snapshot).where(Snapshot.run_id == run.id))
    assert snapshot is None


def test_multiple_watches_handled_independently(db):
    """7. Multiple independent watches execute and poll without interference."""
    _, watch_a = create_test_watch(db, url="https://www.daraz.pk/products/item-a")
    _, watch_b = create_test_watch(db, url="https://www.daraz.pk/products/item-b")

    run_a = RunCreationService(db).create(watch_a.id)
    run_b = RunCreationService(db).create(watch_b.id)

    mock_adapter = MockBrightDataAdapter(preset_status="ready")
    worker = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=mock_adapter))

    res_a = worker.process_run(run_a.id)
    res_b = worker.process_run(run_b.id)

    assert res_a.status == "succeeded"
    assert res_b.status == "succeeded"
    assert res_a.watch_id == watch_a.id
    assert res_b.watch_id == watch_b.id
    assert len(mock_adapter.triggered_calls) == 2
