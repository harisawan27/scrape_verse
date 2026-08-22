import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Base, Change, Snapshot, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import ActiveRunExistsError, MockRunExecutor, RunCreationService


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


def make_watch(db):
    repository = WatchRepository(db)
    user = repository.create_user(UserCreate(email=f"run-{uuid.uuid4()}@example.com"))
    return repository.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/chair",
                "title": "Office chair",
                "instruction": "Alert when price is below PKR 2500.",
                "monitoring_spec": {"field": "price", "currency": "PKR", "value": 2500},
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": datetime(2026, 8, 18, tzinfo=timezone.utc).isoformat(),
                },
            }
        )
    )


def create_and_execute(db, watch, payload=None, fail=False, scheduled_for=None):
    run = RunCreationService(db).create(watch.id, scheduled_for=scheduled_for)
    return MockRunExecutor(db).execute(run, payload=payload, fail=fail)


def test_watch_run_creates_snapshot_and_succeeds(db):
    watch = make_watch(db)
    run = create_and_execute(db, watch)

    snapshot = db.scalar(select(Snapshot).where(Snapshot.run_id == run.id))
    assert run.status == "succeeded"
    assert snapshot is not None
    assert snapshot.watch_id == watch.id
    assert snapshot.metadata_["source"] == "mock"


def test_failed_run_has_no_successful_snapshot(db):
    watch = make_watch(db)
    run = create_and_execute(db, watch, fail=True)

    assert run.status == "failed"
    assert run.error_detail == "mock extraction failed"
    assert db.scalar(select(Snapshot).where(Snapshot.run_id == run.id)) is None


def test_duplicate_active_runs_are_rejected(db):
    watch = make_watch(db)
    RunCreationService(db).create(watch.id)

    with pytest.raises(ActiveRunExistsError):
        RunCreationService(db).create(watch.id)

    assert db.scalar(select(WatchRun).where(WatchRun.watch_id == watch.id, WatchRun.status == "pending")) is not None


def test_first_snapshot_has_no_changes(db):
    watch = make_watch(db)
    run = create_and_execute(db, watch, payload={"price": 3000, "currency": "PKR"})

    assert db.scalars(select(Change).where(Change.run_id == run.id)).all() == []


def test_changed_second_snapshot_persists_changes(db):
    watch = make_watch(db)
    create_and_execute(
        db, watch, payload={"price": 3000, "currency": "PKR"}, scheduled_for=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc)
    )
    second = create_and_execute(
        db,
        watch,
        payload={"price": 2400, "currency": "PKR", "availability": "in_stock"},
        scheduled_for=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc),
    )

    changes = db.scalars(select(Change).where(Change.run_id == second.id).order_by(Change.change_type)).all()
    assert {change.change_type for change in changes} == {"field_added", "value_changed"}
    assert any(change.details["path"] == "$.price" for change in changes)


def test_identical_second_snapshot_creates_no_changes(db):
    watch = make_watch(db)
    payload = {"price": 3000, "currency": "PKR"}
    create_and_execute(db, watch, payload=payload, scheduled_for=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc))
    second = create_and_execute(db, watch, payload=payload, scheduled_for=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc))

    assert db.scalars(select(Change).where(Change.run_id == second.id)).all() == []


def test_target_identity_mismatch_fails_run(db):
    from app.integrations.bright_data import MockBrightDataAdapter
    from app.services.runs import BrightDataRunExecutor

    repository = WatchRepository(db)
    user = repository.create_user(UserCreate(email=f"daraz-{uuid.uuid4()}@example.com"))
    watch = repository.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://www.daraz.pk/products/test-item-i519675927-s3479476860.html",
                "title": "Daraz Product",
                "instruction": "Alert when price < 1000",
                "monitoring_spec": {"field": "price", "currency": "PKR", "value": 1000},
                "schedule": {
                    "cadence": "hourly",
                    "timezone": "UTC",
                    "next_due_at": datetime(2026, 8, 18, tzinfo=timezone.utc).isoformat(),
                },
            }
        )
    )

    # Return data for a DIFFERENT product ID: i999999999
    adapter = MockBrightDataAdapter(
        preset_data=[
            {
                "url": "https://www.daraz.pk/products/wrong-item-i999999999.html",
                "title": "Wrong Product",
                "price": 1000,
                "currency": "PKR",
            }
        ]
    )

    run = RunCreationService(db).create(watch.id)
    executor = BrightDataRunExecutor(db, adapter=adapter, default_collector_id="c_test")
    finished_run = executor.execute(run)

    assert finished_run.status == "failed"
    assert finished_run.error_code == "target_identity_mismatch"
    assert "Target product ID '519675927' does not match" in (finished_run.error_detail or "")


def test_watch_overview_returns_all_runs_and_alerts(db):
    repository = WatchRepository(db)
    watch = make_watch(db)

    # Create 3 runs
    create_and_execute(db, watch, payload={"price": 3000, "currency": "PKR"}, scheduled_for=datetime(2026, 8, 18, 10, 0, tzinfo=timezone.utc))
    create_and_execute(db, watch, payload={"price": 2800, "currency": "PKR"}, scheduled_for=datetime(2026, 8, 18, 11, 0, tzinfo=timezone.utc))
    create_and_execute(db, watch, payload={"price": 2400, "currency": "PKR"}, scheduled_for=datetime(2026, 8, 18, 12, 0, tzinfo=timezone.utc))

    overview = repository.get_watch_overview(watch.id)
    assert overview is not None
    assert len(overview.runs) == 3
    # Check newest first
    assert overview.runs[0].scheduled_for > overview.runs[1].scheduled_for
    # Check attached snapshot
    assert overview.runs[0].snapshot is not None
    assert overview.runs[0].snapshot.payload["price"] == 2400


