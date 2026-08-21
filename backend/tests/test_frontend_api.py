import uuid
from datetime import datetime, timezone
import pytest
from fastapi.testclient import TestClient

from app.models import Alert, ScraperRepair, Snapshot, Watch, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate, WatchUpdate
from app.services.overview import (
    derive_health_status,
    extract_domain,
    extract_product_current_value,
)
from app.services.runs import MockRunExecutor, RunCreationService



def create_user_and_watch(client, url="https://www.daraz.pk/products/office-chair-i111.html", title="Office Chair", user_id=None):
    if user_id is None:
        user_res = client.post("/v1/users", json={"email": f"user-{uuid.uuid4()}@example.com"})
        user_id = user_res.json()["id"]

    client.headers["X-User-Id"] = user_id

    watch_payload = {
        "user_id": user_id,
        "url": url,
        "title": title,
        "instruction": "Track price drop below 2500",
        "monitoring_spec": {
            "vertical": "product",
            "currency": "PKR",
            "cadence_minutes": 30,
            "collector_id": "c_msz0zrtw29tjzhzakl",
            "rules": [{"type": "price_below", "field": "price", "value": 2500, "currency": "PKR"}],
        },
        "schedule": {
            "cadence": "custom",
            "timezone": "Asia/Karachi",
            "next_due_at": "2026-08-20T10:00:00+05:00",
        },
        "status": "active",
    }
    watch_res = client.post("/v1/watches", json=watch_payload)
    return user_id, watch_res.json()




def test_extract_domain_and_current_value():
    assert extract_domain("https://www.daraz.pk/products/item-1.html") == "daraz.pk"
    assert extract_domain("https://daraz.pk/products/item-2.html") == "daraz.pk"
    assert extract_domain("https://subdomain.example.com/page") == "subdomain.example.com"

    mock_snapshot = Snapshot(
        run_id="run-1",
        watch_id="w-1",
        payload={
            "price": 2499.0,
            "currency": "PKR",
            "availability": "in_stock",
            "title": "Ergonomic Chair",
            "seller": "SuperStore",
            "rating": 4.8,
            "reviews_count": 120,
        },
        captured_at=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
        extracted_at=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc),
    )
    val = extract_product_current_value(mock_snapshot)
    assert val is not None
    assert val.price == 2499.0
    assert val.currency == "PKR"
    assert val.availability == "in_stock"
    assert val.rating == 4.8
    assert val.reviews_count == 120


def test_health_status_precedence_rules():
    watch = Watch(
        user_id="u-1",
        url="https://www.daraz.pk/products/1",
        title="Item",
        instruction="Track",
        monitoring_spec={},
        status="active",
    )

    # 1. Newly created active watch -> healthy
    assert derive_health_status(watch, runs=[]) == "healthy"

    # 2. Paused watch -> paused
    watch.status = "paused"
    assert derive_health_status(watch, runs=[]) == "paused"
    watch.status = "active"

    # 3. Active repair (in_progress) on a failed run -> repairing
    active_repair = ScraperRepair(
        watch_id="w-1",
        run_id="r-1",
        collector_id="c-1",
        repair_prompt="Fix price",
        status="in_progress",
    )
    failed_initial_run = WatchRun(watch_id="w-1", status="failed", scheduled_for=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc))
    assert derive_health_status(watch, runs=[failed_initial_run], repairs=[active_repair]) == "repairing"

    # Recovery: If a newer successful run occurred after repair, health status is healthy
    recovery_run = WatchRun(watch_id="w-1", status="succeeded", scheduled_for=datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc))
    assert derive_health_status(watch, runs=[recovery_run, failed_initial_run], repairs=[active_repair]) == "healthy"

    # 4. Active running run -> running
    running_run = WatchRun(watch_id="w-1", status="running", scheduled_for=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc))
    resolved_repair = ScraperRepair(
        watch_id="w-1",
        run_id="r-1",
        collector_id="c-1",
        repair_prompt="Fix price",
        status="resolved",
    )
    assert derive_health_status(watch, runs=[running_run, failed_initial_run], repairs=[resolved_repair]) == "running"

    # 5. Latest terminal run failed -> failed
    failed_run = WatchRun(watch_id="w-1", status="failed", scheduled_for=datetime(2026, 8, 19, 12, 0, tzinfo=timezone.utc))
    assert derive_health_status(watch, runs=[failed_run, failed_initial_run], repairs=[resolved_repair]) == "failed"

    # 6. Latest terminal run succeeded -> healthy
    newer_success_run = WatchRun(watch_id="w-1", status="succeeded", scheduled_for=datetime(2026, 8, 19, 13, 0, tzinfo=timezone.utc))
    assert derive_health_status(watch, runs=[newer_success_run, failed_run], repairs=[resolved_repair]) == "healthy"



def test_watch_summary_card_contains_latest_price_from_snapshot(client):
    user_id, watch = create_user_and_watch(client)
    watch_id = watch["id"]

    session_factory = client.session_factory

    with session_factory() as db:
        creation = RunCreationService(db)
        executor = MockRunExecutor(db)
        run = creation.create(watch_id)
        executor.execute(
            run,
            payload={
                "url": watch["url"],
                "title": watch["title"],
                "price": 2350.0,
                "currency": "PKR",
                "availability": "in_stock",
                "rating": 4.5,
                "reviews_count": 42,
            },
        )

    # Fetch summary list
    resp = client.get(f"/v1/watches?user_id={user_id}")
    assert resp.status_code == 200
    summaries = resp.json()
    assert len(summaries) == 1
    card = summaries[0]
    assert card["id"] == watch_id
    assert card["domain"] == "daraz.pk"
    assert card["health_status"] == "healthy"
    assert card["cadence_minutes"] == 30
    assert card["latest_value"] is not None
    assert card["latest_value"]["price"] == 2350.0
    assert card["latest_value"]["currency"] == "PKR"
    assert card["latest_value"]["availability"] == "in_stock"
    assert card["latest_value"]["rating"] == 4.5
    assert card["latest_value"]["reviews_count"] == 42


def test_failed_run_does_not_corrupt_latest_successful_snapshot_value(client):
    user_id, watch = create_user_and_watch(client)
    watch_id = watch["id"]

    session_factory = client.session_factory

    with session_factory() as db:
        creation = RunCreationService(db)
        executor = MockRunExecutor(db)

        # Run 1: Successful baseline
        run1 = creation.create(watch_id, scheduled_for=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc))
        executor.execute(
            run1,
            payload={"url": watch["url"], "title": watch["title"], "price": 2800.0, "currency": "PKR"},
        )

        # Run 2: Failed run
        run2 = creation.create(watch_id, scheduled_for=datetime(2026, 8, 19, 10, 30, tzinfo=timezone.utc))
        run2.status = "failed"
        run2.error_code = "bright_data_transport_error"
        db.commit()

    resp = client.get(f"/v1/watches?user_id={user_id}")
    assert resp.status_code == 200
    card = resp.json()[0]
    # Health status should reflect latest terminal run failed
    assert card["health_status"] == "failed"
    # Latest value must retain the last successful snapshot (2800.0), NOT null/corrupted
    assert card["latest_value"] is not None
    assert card["latest_value"]["price"] == 2800.0


def test_watch_overview_aggregates_snapshot_run_event_and_stats(client):
    user_id, watch = create_user_and_watch(client)
    watch_id = watch["id"]

    session_factory = client.session_factory

    with session_factory() as db:
        creation = RunCreationService(db)
        executor = MockRunExecutor(db)

        # Run 1: Baseline
        run1 = creation.create(watch_id, scheduled_for=datetime(2026, 8, 19, 8, 0, tzinfo=timezone.utc))
        executor.execute(
            run1,
            payload={"url": watch["url"], "title": watch["title"], "price": 3000.0, "currency": "PKR"},
        )

        # Run 2: Price drop below 2500 -> Alert generated
        run2 = creation.create(watch_id, scheduled_for=datetime(2026, 8, 19, 8, 30, tzinfo=timezone.utc))
        executor.execute(
            run2,
            payload={"url": watch["url"], "title": watch["title"], "price": 2200.0, "currency": "PKR"},
        )

    # Call single overview endpoint
    resp = client.get(f"/v1/watches/{watch_id}/overview", headers={"X-User-Id": user_id})
    assert resp.status_code == 200
    overview = resp.json()
    assert overview["watch"]["id"] == watch_id
    assert overview["health_status"] == "healthy"
    assert overview["latest_snapshot"]["payload"]["price"] == 2200.0
    assert overview["latest_run"]["id"] is not None
    assert overview["latest_event"]["event_type"] in ("price_threshold_crossed", "price_decreased")
    assert overview["latest_value"]["price"] == 2200.0

    assert overview["stats"]["total_runs"] == 2
    assert overview["stats"]["successful_runs"] == 2
    assert overview["stats"]["failed_runs"] == 0
    assert overview["stats"]["total_events"] >= 1


def test_global_activity_feed_cross_watch_newest_first(client):
    user_id, watch1 = create_user_and_watch(client, url="https://www.daraz.pk/products/item-1.html", title="Gaming Chair")
    _, watch2 = create_user_and_watch(client, url="https://www.daraz.pk/products/item-2.html", title="Wireless Mouse", user_id=user_id)


    session_factory = client.session_factory

    with session_factory() as db:
        # Create alert for Watch 1 (earlier)
        alert1 = Alert(
            watch_id=watch1["id"],
            event_type="price_threshold_crossed",
            summary="Gaming Chair price dropped to Rs 2,200",
            details={"previous_value": 3000, "current_value": 2200},
            status="triggered",
            created_at=datetime(2026, 8, 19, 10, 0, tzinfo=timezone.utc),
        )
        # Create alert for Watch 2 (later)
        alert2 = Alert(
            watch_id=watch2["id"],
            event_type="back_in_stock",
            summary="Wireless Mouse is back in stock",
            details={"availability": "in_stock"},
            status="triggered",
            created_at=datetime(2026, 8, 19, 11, 0, tzinfo=timezone.utc),
        )
        db.add_all([alert1, alert2])
        db.commit()

    resp = client.get(f"/v1/activity?user_id={user_id}&limit=10", headers={"X-User-Id": user_id})
    assert resp.status_code == 200
    feed = resp.json()
    assert len(feed) == 2
    # Newest first: alert2 (11:00) then alert1 (10:00)
    assert feed[0]["watch_id"] == watch2["id"]
    assert feed[0]["watch_title"] == "Wireless Mouse"
    assert feed[0]["event_type"] == "back_in_stock"

    assert feed[1]["watch_id"] == watch1["id"]
    assert feed[1]["watch_title"] == "Gaming Chair"
    assert feed[1]["event_type"] == "price_threshold_crossed"


def test_watch_update_cadence_and_status(client):
    user_id, watch = create_user_and_watch(client)
    watch_id = watch["id"]
    headers = {"X-User-Id": user_id}

    # Update cadence from custom to daily
    resp = client.patch(
        f"/v1/watches/{watch_id}",
        json={"schedule": {"cadence": "daily", "timezone": "Asia/Karachi"}},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["schedule"]["cadence"] == "daily"
    assert data["schedule"]["timezone"] == "Asia/Karachi"

    # Update status to paused -> schedule disabled
    resp_pause = client.patch(f"/v1/watches/{watch_id}", json={"status": "paused"}, headers=headers)
    assert resp_pause.status_code == 200
    assert resp_pause.json()["status"] == "paused"
    assert resp_pause.json()["schedule"]["enabled"] is False

    # Check summary card reflects paused
    resp_sum = client.get(f"/v1/watches?user_id={user_id}", headers=headers)
    assert resp_sum.json()[0]["health_status"] == "paused"

    # Reactivate
    resp_act = client.patch(f"/v1/watches/{watch_id}", json={"status": "active"}, headers=headers)
    assert resp_act.status_code == 200
    assert resp_act.json()["status"] == "active"
    assert resp_act.json()["schedule"]["enabled"] is True


def test_watch_update_monitoring_rules(client):
    user_id, watch = create_user_and_watch(client)
    watch_id = watch["id"]
    headers = {"X-User-Id": user_id}

    new_spec = {
        "vertical": "product",
        "currency": "PKR",
        "collector_id": "c_msz0zrtw29tjzhzakl",
        "rules": [
            {"type": "price_below", "field": "price", "value": 1999.0, "currency": "PKR"},
            {"type": "back_in_stock", "field": "availability"},
        ],
    }
    resp = client.patch(f"/v1/watches/{watch_id}", json={"monitoring_spec": new_spec}, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data["monitoring_spec"]["rules"]) == 2
    assert data["monitoring_spec"]["rules"][0]["value"] == 1999.0



def test_cors_preflight_and_headers(client):
    # Test preflight OPTIONS request
    headers = {
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "Content-Type",
    }
    resp = client.options("/v1/watches", headers=headers)
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
    assert resp.headers.get("access-control-allow-credentials") == "true"
