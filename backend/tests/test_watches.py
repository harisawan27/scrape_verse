from datetime import datetime, timezone


def create_user(client):
    response = client.post("/v1/users", json={"email": "radar@example.com"})
    assert response.status_code == 201
    return response.json()["id"]


def watch_payload(user_id: str) -> dict:
    return {
        "user_id": user_id,
        "url": "https://example.com/chair",
        "title": "Office chair",
        "instruction": "Alert me when price is below PKR 2500.",
        "monitoring_spec": {"field": "price", "operator": "lt", "currency": "PKR", "value": 2500},
        "schedule": {
            "cadence": "daily",
            "timezone": "Asia/Karachi",
            "next_due_at": datetime(2026, 8, 18, 9, tzinfo=timezone.utc).isoformat(),
        },
    }


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_watch_crud(client):
    user_id = create_user(client)
    headers = {"X-User-Id": user_id}
    created = client.post("/v1/watches", json=watch_payload(user_id), headers=headers)
    assert created.status_code == 201
    watch = created.json()
    assert watch["status"] == "active"
    assert watch["schedule"]["cadence"] == "daily"

    listed = client.get(f"/v1/watches?user_id={user_id}", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [watch["id"]]

    updated = client.patch(
        f"/v1/watches/{watch['id']}",
        json={"title": "Ergonomic office chair", "status": "paused", "schedule": {"cadence": "weekly", "timezone": "Asia/Karachi", "next_due_at": "2026-08-25T09:00:00+00:00"}},
        headers=headers,
    )
    assert updated.status_code == 200
    assert updated.json()["title"] == "Ergonomic office chair"
    assert updated.json()["status"] == "paused"
    assert updated.json()["schedule"]["cadence"] == "weekly"

    deleted = client.delete(f"/v1/watches/{watch['id']}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/v1/watches/{watch['id']}", headers=headers).status_code == 404


def test_watch_requires_existing_user_and_valid_schedule(client):
    payload = watch_payload("missing-user")
    assert client.post("/v1/watches", json=payload, headers={"X-User-Id": "missing-user"}).status_code == 404

    user_id = create_user(client)
    payload = watch_payload(user_id)
    payload["schedule"]["timezone"] = "Not/AZone"
    assert client.post("/v1/watches", json=payload, headers={"X-User-Id": user_id}).status_code == 422


def test_duplicate_user_email_is_rejected(client):
    create_user(client)
    assert client.post("/v1/users", json={"email": "radar@example.com"}).status_code == 409


def test_watch_run_api_endpoints(client):
    user_id = create_user(client)
    headers = {"X-User-Id": user_id}
    created = client.post("/v1/watches", json=watch_payload(user_id), headers=headers)
    assert created.status_code == 201
    watch_id = created.json()["id"]

    # Trigger a run via API
    run_resp = client.post(f"/v1/watches/{watch_id}/runs", headers=headers)
    assert run_resp.status_code == 201
    run_data = run_resp.json()
    assert run_data["watch_id"] == watch_id
    assert run_data["status"] == "succeeded"
    assert run_data["snapshot"] is not None
    assert run_data["snapshot"]["payload"]["url"] == "https://example.com/chair"

    # List runs for watch
    list_runs_resp = client.get(f"/v1/watches/{watch_id}/runs", headers=headers)
    assert list_runs_resp.status_code == 200
    runs = list_runs_resp.json()
    assert len(runs) == 1
    assert runs[0]["id"] == run_data["id"]

    # Get single run by ID
    get_run_resp = client.get(f"/v1/runs/{run_data['id']}", headers=headers)
    assert get_run_resp.status_code == 200
    assert get_run_resp.json()["id"] == run_data["id"]

    # List changes for watch (first run should have 0 changes)
    changes_resp = client.get(f"/v1/watches/{watch_id}/changes", headers=headers)
    assert changes_resp.status_code == 200
    assert changes_resp.json() == []


def test_scheduler_api_endpoints(client):
    from datetime import timedelta
    user_id = create_user(client)
    headers = {"X-User-Id": user_id}
    payload = watch_payload(user_id)
    # Ensure next_due_at is strictly in the past relative to current system time
    payload["schedule"]["next_due_at"] = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    created = client.post("/v1/watches", json=payload, headers=headers)
    assert created.status_code == 201

    # Check scheduler status
    status_resp = client.get("/v1/scheduler/status")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "ready"

    # Trigger scheduler tick via API
    tick_resp = client.post("/v1/scheduler/tick")
    assert tick_resp.status_code == 200
    executed = tick_resp.json()
    assert len(executed) >= 1
    assert executed[0]["status"] in {"running", "succeeded"}


def test_watch_events_api_endpoint(client):
    user_id = create_user(client)
    headers = {"X-User-Id": user_id}
    payload = watch_payload(user_id)
    payload["monitoring_spec"] = {
        "rules": [{"type": "price_below", "field": "price", "value": 2500, "currency": "PKR"}]
    }
    created = client.post("/v1/watches", json=payload, headers=headers)
    assert created.status_code == 201
    watch_id = created.json()["id"]

    # Initial events is empty
    events_resp = client.get(f"/v1/watches/{watch_id}/events", headers=headers)
    assert events_resp.status_code == 200
    assert events_resp.json() == []

    alerts_resp = client.get(f"/v1/watches/{watch_id}/alerts", headers=headers)
    assert alerts_resp.status_code == 200
    assert alerts_resp.json() == []


def test_watch_repairs_api_endpoint(client):
    user_id = create_user(client)
    headers = {"X-User-Id": user_id}
    payload = watch_payload(user_id)
    created = client.post("/v1/watches", json=payload, headers=headers)
    assert created.status_code == 201
    watch_id = created.json()["id"]

    repairs_resp = client.get(f"/v1/watches/{watch_id}/repairs", headers=headers)
    assert repairs_resp.status_code == 200
    assert repairs_resp.json() == []
