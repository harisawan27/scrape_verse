import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.integrations.bright_data import MockBrightDataAdapter
from app.integrations.bright_data.types import BrightDataAuthError
from app.models import Base, ScraperRepair, Snapshot, Watch, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import BrightDataRunExecutor, RunCreationService
from app.services.self_healing import (
    SelfHealingService,
    generate_repair_prompt,
    validate_product_payload,
)
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


def make_watch(db, collector_id="c_test_custom_123"):
    repo = WatchRepository(db)
    user = repo.create_user(UserCreate(email=f"heal-{uuid.uuid4()}@example.com"))
    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/product/xyz",
                "title": "Self Healing Product",
                "instruction": "Track price changes",
                "monitoring_spec": {
                    "collector_id": collector_id,
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
    return user, watch


def test_validate_product_payload_classification():
    """Requirement: Validate product schema and identify missing required fields."""
    # 1. Valid payload
    valid_payload = {
        "url": "https://example.com/p1",
        "title": "Wireless Earbuds",
        "price": 3499.0,
        "currency": "PKR",
        "availability": "in_stock",
    }
    is_valid, missing = validate_product_payload(valid_payload)
    assert is_valid is True
    assert missing == []

    # 2. price = null is an extraction failure
    null_price_payload = {
        "url": "https://example.com/p1",
        "title": "Wireless Earbuds",
        "price": None,
        "currency": "PKR",
    }
    is_valid, missing = validate_product_payload(null_price_payload)
    assert is_valid is False
    assert "price" in missing

    # 3. Missing title and invalid price
    missing_fields_payload = {
        "url": "https://example.com/p1",
        "title": "",
        "price": "N/A",
        "currency": "PKR",
    }
    is_valid, missing = validate_product_payload(missing_fields_payload)
    assert is_valid is False
    assert "title" in missing
    assert "price" in missing


def test_deterministic_repair_prompt_generation():
    """Requirement: Generate structured repair prompt without LLM."""
    prompt = generate_repair_prompt(
        collector_id="c_daraz_product",
        target_url="https://example.com/item/100",
        missing_fields=["price", "availability"],
    )
    assert "c_daraz_product" not in prompt or "item/100" in prompt
    assert "price, availability" in prompt
    assert "Repair the scraper extraction selectors/logic" in prompt
    assert "preserving the structured output schema" in prompt


def test_api_network_error_does_not_trigger_self_healing(db):
    """Requirement: API/Transport failure marks run failed without triggering self-healing."""
    _, watch = make_watch(db)
    creation = RunCreationService(db)
    run = creation.create(watch.id)

    # Adapter that fails on trigger
    adapter = MockBrightDataAdapter(fail_trigger=True)
    executor = BrightDataRunExecutor(db, adapter=adapter, default_collector_id="c_test_123")

    executed_run = executor.execute(run)
    assert executed_run.status == "failed"
    assert executed_run.error_code == "bright_data_trigger_failed"

    # Verify 0 repair records created
    repairs = db.scalars(select(ScraperRepair).where(ScraperRepair.watch_id == watch.id)).all()
    assert len(repairs) == 0


def test_schema_failure_initiates_scraper_repair_and_creates_no_snapshot(db):
    """Requirement: Extraction failure (null price) creates a ScraperRepair and 0 snapshots."""
    _, watch = make_watch(db)
    creation = RunCreationService(db)
    run = creation.create(watch.id)

    # Scraper returned result where price is null (e.g. DOM changed)
    corrupted_data = [
        {
            "url": watch.url,
            "title": watch.title,
            "price": None,  # Extraction failure!
            "currency": "PKR",
            "availability": "in_stock",
        }
    ]
    adapter = MockBrightDataAdapter(preset_data=corrupted_data, preset_status="ready")
    executor = BrightDataRunExecutor(db, adapter=adapter, default_collector_id="c_test_custom_123")

    # Pending -> triggers collection -> polls ready -> detects schema failure -> triggers repair -> marks failed
    run = executor.execute(run)
    assert run.status == "failed"
    assert run.error_code == "extraction_schema_failure"
    assert run.bright_data_collection_id is not None

    # Verify 0 snapshots created
    snapshots = db.scalars(select(Snapshot).where(Snapshot.watch_id == watch.id)).all()
    assert len(snapshots) == 0

    # Verify 1 ScraperRepair created
    repairs = list(db.scalars(select(ScraperRepair).where(ScraperRepair.watch_id == watch.id)).all())
    assert len(repairs) == 1
    repair = repairs[0]
    assert repair.run_id == run.id
    assert repair.collector_id == "c_test_custom_123"
    assert repair.status == "in_progress"
    assert "price" in repair.missing_fields
    assert len(adapter.refactor_calls) == 1



def test_duplicate_processing_does_not_create_duplicate_repairs(db):
    """Requirement: Idempotency - repeated ticks do not duplicate repair requests."""
    _, watch = make_watch(db)
    creation = RunCreationService(db)
    run = creation.create(watch.id)

    corrupted_data = [{"url": watch.url, "title": watch.title, "price": None, "currency": "PKR"}]
    adapter = MockBrightDataAdapter(preset_data=corrupted_data, preset_status="ready")
    worker = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=adapter, default_collector_id="c_test_custom_123"))

    # Initial processing
    worker.process_run(run.id)  # pending -> running
    worker.process_run(run.id)  # running -> failed with repair

    repairs1 = list(db.scalars(select(ScraperRepair).where(ScraperRepair.watch_id == watch.id)).all())
    assert len(repairs1) == 1

    # Repeat processing on terminal run
    worker.process_run(run.id)
    repairs2 = list(db.scalars(select(ScraperRepair).where(ScraperRepair.watch_id == watch.id)).all())
    assert len(repairs2) == 1
    assert len(adapter.refactor_calls) == 1


def test_worker_polls_and_advances_repair_lifecycle(db):
    """Requirement: Worker tick polls in-progress repairs and transitions to applied/ready."""
    _, watch = make_watch(db)
    creation = RunCreationService(db)
    run = creation.create(watch.id)

    corrupted_data = [{"url": watch.url, "title": watch.title, "price": None, "currency": "PKR"}]
    adapter = MockBrightDataAdapter(
        preset_data=corrupted_data,
        preset_status="ready",
        preset_refactor_status="pending_answer",
    )
    worker = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=adapter, default_collector_id="c_test_custom_123"))

    worker.process_run(run.id)
    worker.process_run(run.id)

    # Worker tick polls active repairs
    tick_result = worker.tick()
    assert "repairs" in tick_result
    assert len(tick_result["repairs"]) >= 1

    repair = db.scalars(select(ScraperRepair).where(ScraperRepair.watch_id == watch.id)).one()
    assert repair.status in {"applied", "ready", "requires_manual_promotion"}
    assert len(adapter.approve_calls) == 1


def test_controlled_end_to_end_self_healing_flow(db):
    """Requirement: Controlled end-to-end self-healing flow (v1 succeeds -> v2 DOM break -> repair -> recovery)."""
    _, watch = make_watch(db)
    creation = RunCreationService(db)

    # Stage 1: v1 works normally
    v1_data = [{"url": watch.url, "title": watch.title, "price": 2999.0, "currency": "PKR", "availability": "in_stock"}]
    adapter_v1 = MockBrightDataAdapter(preset_data=v1_data, preset_status="ready")
    worker_v1 = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=adapter_v1, default_collector_id="c_test_custom_123"))

    run1 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc))
    worker_v1.process_run(run1.id)  # pending -> running
    run1 = worker_v1.process_run(run1.id)  # running -> succeeded
    assert run1.status == "succeeded"

    # Stage 2: v2 DOM changes -> price extraction breaks (price is None)
    v2_broken_data = [{"url": watch.url, "title": watch.title, "price": None, "currency": "PKR", "availability": "in_stock"}]
    adapter_v2 = MockBrightDataAdapter(
        preset_data=v2_broken_data,
        preset_status="ready",
        preset_refactor_status="ready",
    )
    worker_v2 = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=adapter_v2, default_collector_id="c_test_custom_123"))

    run2 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    worker_v2.process_run(run2.id)
    run2 = worker_v2.process_run(run2.id)
    assert run2.status == "failed"
    assert run2.error_code == "extraction_schema_failure"

    # Repair recorded in DB
    repair = db.scalars(select(ScraperRepair).where(ScraperRepair.run_id == run2.id)).one()
    assert repair.status == "in_progress"

    # Worker tick advances repair
    worker_v2.tick()
    db.refresh(repair)
    assert repair.status in {"ready", "applied"}

    # Stage 3: Repaired scraper executed -> recovers and creates valid snapshot
    v3_healed_data = [{"url": watch.url, "title": watch.title, "price": 2799.0, "currency": "PKR", "availability": "in_stock"}]
    adapter_v3 = MockBrightDataAdapter(preset_data=v3_healed_data, preset_status="ready")
    worker_v3 = WorkerService(db, executor=BrightDataRunExecutor(db, adapter=adapter_v3, default_collector_id="c_test_custom_123"))

    run3 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 20, 9, 0, tzinfo=timezone.utc))
    worker_v3.process_run(run3.id)
    run3 = worker_v3.process_run(run3.id)
    assert run3.status == "succeeded"

    # Active repair is automatically reconciled to succeeded
    db.refresh(repair)
    assert repair.status == "succeeded"

    snapshots = list(db.scalars(select(Snapshot).where(Snapshot.watch_id == watch.id).order_by(Snapshot.captured_at.asc())).all())
    assert len(snapshots) == 2  # exactly 2 snapshots (v1 and healed v3, 0 snapshots for broken v2)
    assert snapshots[0].payload["price"] == 2999.0
    assert snapshots[1].payload["price"] == 2799.0
