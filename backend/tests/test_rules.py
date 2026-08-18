import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.models import Alert, Base, Snapshot, Watch, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.rules import RuleEvaluator
from app.services.runs import MockRunExecutor, RunCreationService


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


def make_watch(db, *, rules=None, threshold=2500, currency="PKR", url="https://example.com/item"):
    repo = WatchRepository(db)
    user = repo.create_user(UserCreate(email=f"rules-{uuid.uuid4()}@example.com"))
    spec = {"field": "price", "currency": currency}
    if rules is not None:
        spec["rules"] = rules
    elif threshold is not None:
        spec["rules"] = [
            {"type": "price_below", "field": "price", "value": threshold, "currency": currency}
        ]

    watch = repo.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": url,
                "title": "Test Product",
                "instruction": f"Alert when price < {threshold}",
                "monitoring_spec": spec,
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )
    return user, watch


def test_first_snapshot_establishes_baseline_with_no_false_crossing(db):
    """Requirement: First Snapshot establishes baseline without false threshold crossing."""
    _, watch = make_watch(db, threshold=2500)
    current_payload = {"url": watch.url, "title": watch.title, "price": 2400, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=current_payload, previous_payload=None)
    assert events == []


def test_price_decrease_above_threshold_produces_no_threshold_crossing(db):
    """5490 -> 4990 = price decrease event, but NO 2500 threshold event."""
    _, watch = make_watch(db, threshold=2500)
    prev_payload = {"url": watch.url, "title": watch.title, "price": 5490, "currency": "PKR"}
    curr_payload = {"url": watch.url, "title": watch.title, "price": 4990, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=curr_payload, previous_payload=prev_payload)
    event_types = [e.event_type for e in events]

    assert "price_decreased" in event_types
    assert "price_threshold_crossed" not in event_types

    price_dec = next(e for e in events if e.event_type == "price_decreased")
    assert price_dec.details["previous_value"] == 5490
    assert price_dec.details["current_value"] == 4990
    assert price_dec.details["drop_amount"] == 500


def test_price_drop_crossing_threshold_triggers_threshold_event(db):
    """2700 -> 2399 with rule < 2500 = threshold event + price decrease."""
    _, watch = make_watch(db, threshold=2500)
    prev_payload = {"url": watch.url, "title": watch.title, "price": 2700, "currency": "PKR"}
    curr_payload = {"url": watch.url, "title": watch.title, "price": 2399, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=curr_payload, previous_payload=prev_payload)
    event_types = [e.event_type for e in events]

    assert "price_threshold_crossed" in event_types
    assert "price_decreased" in event_types

    threshold_event = next(e for e in events if e.event_type == "price_threshold_crossed")
    assert threshold_event.details["previous_value"] == 2700
    assert threshold_event.details["current_value"] == 2399
    assert threshold_event.details["rule_value"] == 2500
    assert threshold_event.details["rule_type"] == "price_below"


def test_subsequent_drop_while_already_below_threshold_does_not_duplicate_threshold_alert(db):
    """2399 -> 2299 = price decrease, but NO duplicate threshold-crossing event."""
    _, watch = make_watch(db, threshold=2500)
    prev_payload = {"url": watch.url, "title": watch.title, "price": 2399, "currency": "PKR"}
    curr_payload = {"url": watch.url, "title": watch.title, "price": 2299, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=curr_payload, previous_payload=prev_payload)
    event_types = [e.event_type for e in events]

    assert "price_decreased" in event_types
    assert "price_threshold_crossed" not in event_types


def test_re_entering_threshold_after_leaving_triggers_new_crossing_event(db):
    """2299 -> 2700 -> 2400: threshold can trigger again after leaving and re-entering."""
    _, watch = make_watch(db, threshold=2500)

    # Step 1: price rises above threshold (2299 -> 2700)
    p1 = {"url": watch.url, "title": watch.title, "price": 2299, "currency": "PKR"}
    p2 = {"url": watch.url, "title": watch.title, "price": 2700, "currency": "PKR"}
    step1_events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    assert [e.event_type for e in step1_events] == ["price_increased"]

    # Step 2: price drops below threshold again (2700 -> 2400)
    p3 = {"url": watch.url, "title": watch.title, "price": 2400, "currency": "PKR"}
    step2_events = RuleEvaluator.evaluate(watch, current_payload=p3, previous_payload=p2)
    step2_types = [e.event_type for e in step2_events]

    assert "price_threshold_crossed" in step2_types
    assert "price_decreased" in step2_types


def test_price_unchanged_produces_no_semantic_price_events(db):
    """Price unchanged = no semantic price event."""
    _, watch = make_watch(db, threshold=2500)
    p1 = {"url": watch.url, "title": watch.title, "price": 2400, "currency": "PKR"}
    p2 = {"url": watch.url, "title": watch.title, "price": 2400, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    assert events == []


def test_null_price_is_safe_and_creates_no_false_threshold_event(db):
    """Null price = safe/no false threshold event."""
    _, watch = make_watch(db, threshold=2500)
    p1 = {"url": watch.url, "title": watch.title, "price": 3000, "currency": "PKR"}
    p2 = {"url": watch.url, "title": watch.title, "price": None, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    assert events == []


def test_currency_mismatch_prevents_false_crossing_alerts(db):
    """Incompatible currencies (PKR vs USD) must not trigger false threshold crossings."""
    _, watch = make_watch(db, threshold=2500, currency="PKR")
    p1 = {"url": watch.url, "title": watch.title, "price": 3000, "currency": "USD"}
    p2 = {"url": watch.url, "title": watch.title, "price": 2400, "currency": "PKR"}

    events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    assert [e.event_type for e in events if e.event_type == "price_threshold_crossed"] == []


def test_availability_in_stock_to_out_of_stock(db):
    """in-stock -> out-of-stock emits availability_changed."""
    rules = [{"type": "availability_changed", "field": "availability"}]
    _, watch = make_watch(db, rules=rules)
    p1 = {"url": watch.url, "title": watch.title, "availability": "in_stock"}
    p2 = {"url": watch.url, "title": watch.title, "availability": "out_of_stock"}

    events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    assert len(events) == 1
    assert events[0].event_type == "availability_changed"
    assert events[0].details["previous_value"] == "in_stock"
    assert events[0].details["current_value"] == "out_of_stock"


def test_out_of_stock_to_in_stock_triggers_back_in_stock_event(db):
    """out-of-stock -> in-stock emits back_in_stock and availability_changed."""
    rules = [
        {"type": "back_in_stock", "field": "availability"},
        {"type": "availability_changed", "field": "availability"},
    ]
    _, watch = make_watch(db, rules=rules)
    p1 = {"url": watch.url, "title": watch.title, "availability": "out_of_stock"}
    p2 = {"url": watch.url, "title": watch.title, "availability": "in_stock"}

    events = RuleEvaluator.evaluate(watch, current_payload=p2, previous_payload=p1)
    event_types = [e.event_type for e in events]
    assert "back_in_stock" in event_types
    assert "availability_changed" in event_types


def test_executor_persists_alerts_idempotently(db):
    """End-to-end run executor creates Alert records in DB and re-execution is idempotent."""
    _, watch = make_watch(db, threshold=2500)
    creation = RunCreationService(db)
    executor = MockRunExecutor(db)

    # Run 1: baseline at 3000
    run1 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 18, 9, 0, tzinfo=timezone.utc))
    executor.execute(run1, payload={"url": watch.url, "title": watch.title, "price": 3000, "currency": "PKR"})
    alerts1 = db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all()
    assert len(alerts1) == 0

    # Run 2: drops to 2399 (crosses below 2500)
    run2 = creation.create(watch.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    executor.execute(run2, payload={"url": watch.url, "title": watch.title, "price": 2399, "currency": "PKR"})

    alerts2 = list(db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all())
    assert len(alerts2) >= 1
    types2 = {a.event_type for a in alerts2}
    assert "price_threshold_crossed" in types2

    # Idempotency check: executing again on terminal run2 changes nothing
    executor.execute(run2)
    alerts_after = list(db.scalars(select(Alert).where(Alert.watch_id == watch.id)).all())
    assert len(alerts_after) == len(alerts2)


def test_multiple_watches_and_rules_remain_isolated(db):
    """Multiple watches evaluate their own distinct rules and snapshot histories."""
    _, watch_a = make_watch(db, threshold=1000, url="https://example.com/a")
    _, watch_b = make_watch(db, threshold=5000, url="https://example.com/b")

    creation = RunCreationService(db)
    executor = MockRunExecutor(db)

    # Baselines
    run_a1 = creation.create(watch_a.id)
    executor.execute(run_a1, payload={"url": watch_a.url, "title": "A", "price": 1500, "currency": "PKR"})
    run_b1 = creation.create(watch_b.id)
    executor.execute(run_b1, payload={"url": watch_b.url, "title": "B", "price": 6000, "currency": "PKR"})

    # Watch A drops to 900 (<1000): triggers A
    run_a2 = creation.create(watch_a.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    executor.execute(run_a2, payload={"url": watch_a.url, "title": "A", "price": 900, "currency": "PKR"})

    # Watch B drops to 5500 (>5000): does NOT trigger threshold on B
    run_b2 = creation.create(watch_b.id, scheduled_for=datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc))
    executor.execute(run_b2, payload={"url": watch_b.url, "title": "B", "price": 5500, "currency": "PKR"})

    alerts_a = list(db.scalars(select(Alert).where(Alert.watch_id == watch_a.id)).all())
    alerts_b = list(db.scalars(select(Alert).where(Alert.watch_id == watch_b.id)).all())

    assert "price_threshold_crossed" in {a.event_type for a in alerts_a}
    assert "price_threshold_crossed" not in {b.event_type for b in alerts_b}
