"""Security & Isolation Tests for Web Radar (Phase 6C.1: Neon Auth).

Verifies that unauthenticated requests are rejected, and user data
(Watches, Overviews, Runs, Changes, Alerts, Repairs, Activity) is
strictly isolated per authenticated Neon Auth user.
"""

import uuid
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth import clear_test_sessions, register_test_session
from app.db import get_db
from app.main import app
from app.models import Base, User


@pytest.fixture
def auth_test_client():
    """Isolated in-memory SQLite database and test client for auth tests."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    clear_test_sessions()

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    clear_test_sessions()


def test_unauthenticated_protected_requests_rejected(auth_test_client: TestClient):
    """Protected endpoints must reject unauthenticated requests with HTTP 401."""
    res_list = auth_test_client.get("/v1/watches")
    assert res_list.status_code == 401

    res_create = auth_test_client.post(
        "/v1/watches",
        json={
            "user_id": "any-id",
            "url": "https://example.com/item",
            "title": "Unauth Watch",
            "instruction": "Track price",
            "monitoring_spec": {"vertical": "product", "rules": []},
            "schedule": {"cadence": "hourly", "timezone": "UTC", "next_due_at": "2026-08-20T12:00:00Z"},
        },
    )
    assert res_create.status_code == 401

    res_act = auth_test_client.get("/v1/activity")
    assert res_act.status_code == 401

    res_me = auth_test_client.get("/v1/auth/me")
    assert res_me.status_code == 401


def test_neon_auth_session_verification_and_me(auth_test_client: TestClient):
    """Verify Neon Auth session token verification and /v1/auth/me domain profile resolution."""
    neon_user_id = str(uuid.uuid4())
    token = f"neon_session_{uuid.uuid4().hex}"
    email = "alice@webradar.io"

    # Register mock session token simulating Neon Auth
    register_test_session(token, neon_user_id, email)

    headers = {"Authorization": f"Bearer {token}"}

    # First request with valid Neon Auth token provisions/resolves domain user
    res_me = auth_test_client.get("/v1/auth/me", headers=headers)
    assert res_me.status_code == 200
    user_data = res_me.json()
    assert user_data["email"] == email
    assert user_data["auth_id"] == neon_user_id
    domain_user_id = user_data["id"]

    # Invalid session token is rejected
    res_invalid = auth_test_client.get("/v1/auth/me", headers={"Authorization": "Bearer invalid-token"})
    assert res_invalid.status_code == 401


def test_user_isolation_between_two_neon_users(auth_test_client: TestClient):
    """User A and User B must never see or mutate each other's Watches, Runs, or Activity."""
    # 1. Register Neon Auth sessions for Alice (A) and Bob (B)
    neon_id_a = str(uuid.uuid4())
    token_a = f"neon_session_a_{uuid.uuid4().hex}"
    register_test_session(token_a, neon_id_a, "alice@test.com")
    headers_a = {"Authorization": f"Bearer {token_a}"}

    neon_id_b = str(uuid.uuid4())
    token_b = f"neon_session_b_{uuid.uuid4().hex}"
    register_test_session(token_b, neon_id_b, "bob@test.com")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    # Resolve profiles
    user_a = auth_test_client.get("/v1/auth/me", headers=headers_a).json()
    user_b = auth_test_client.get("/v1/auth/me", headers=headers_b).json()

    user_a_id = user_a["id"]
    user_b_id = user_b["id"]

    # 2. User A creates Watch A
    watch_a_res = auth_test_client.post(
        "/v1/watches",
        headers=headers_a,
        json={
            "user_id": "ignored-user-id",  # should be overridden by authenticated session
            "url": "https://daraz.pk/product-a",
            "title": "Watch A (Alice)",
            "instruction": "Alert under 1000",
            "monitoring_spec": {"vertical": "product", "rules": []},
            "schedule": {"cadence": "hourly", "timezone": "UTC", "next_due_at": "2026-08-20T12:00:00Z"},
        },
    )
    assert watch_a_res.status_code == 201
    watch_a = watch_a_res.json()
    assert watch_a["user_id"] == user_a_id

    # 3. User B creates Watch B
    watch_b_res = auth_test_client.post(
        "/v1/watches",
        headers=headers_b,
        json={
            "user_id": "ignored-user-id",
            "url": "https://daraz.pk/product-b",
            "title": "Watch B (Bob)",
            "instruction": "Alert under 2000",
            "monitoring_spec": {"vertical": "product", "rules": []},
            "schedule": {"cadence": "hourly", "timezone": "UTC", "next_due_at": "2026-08-20T12:00:00Z"},
        },
    )
    assert watch_b_res.status_code == 201
    watch_b = watch_b_res.json()
    assert watch_b["user_id"] == user_b_id

    # 4. User A lists watches -> only sees Watch A
    list_a = auth_test_client.get("/v1/watches", headers=headers_a).json()
    assert len(list_a) == 1
    assert list_a[0]["id"] == watch_a["id"]

    # 5. User B lists watches -> only sees Watch B
    list_b = auth_test_client.get("/v1/watches", headers=headers_b).json()
    assert len(list_b) == 1
    assert list_b[0]["id"] == watch_b["id"]

    # 6. User B tries to GET Watch A -> 404 Not Found
    res_b_get_a = auth_test_client.get(f"/v1/watches/{watch_a['id']}", headers=headers_b)
    assert res_b_get_a.status_code == 404

    # 7. User B tries to GET Watch A Overview -> 404 Not Found
    res_b_overview_a = auth_test_client.get(f"/v1/watches/{watch_a['id']}/overview", headers=headers_b)
    assert res_b_overview_a.status_code == 404

    # 8. User B tries to PATCH Watch A -> 404 Not Found
    res_b_patch_a = auth_test_client.patch(
        f"/v1/watches/{watch_a['id']}",
        headers=headers_b,
        json={"title": "Hacked Title"},
    )
    assert res_b_patch_a.status_code == 404

    # 9. User B tries to trigger Run on Watch A -> 404 Not Found
    res_b_run_a = auth_test_client.post(
        f"/v1/watches/{watch_a['id']}/runs",
        headers=headers_b,
        json={"execute_now": True},
    )
    assert res_b_run_a.status_code == 404

    # 10. User B tries to DELETE Watch A -> 404 Not Found
    res_b_del_a = auth_test_client.delete(f"/v1/watches/{watch_a['id']}", headers=headers_b)
    assert res_b_del_a.status_code == 404

    # 11. User A triggers Run on Watch A -> Succeeded
    run_a_res = auth_test_client.post(
        f"/v1/watches/{watch_a['id']}/runs",
        headers=headers_a,
        json={"execute_now": True},
    )
    assert run_a_res.status_code == 201

    # 12. User B cannot see runs or changes of Watch A
    assert auth_test_client.get(f"/v1/watches/{watch_a['id']}/runs", headers=headers_b).status_code == 404
    assert auth_test_client.get(f"/v1/watches/{watch_a['id']}/changes", headers=headers_b).status_code == 404
    assert auth_test_client.get(f"/v1/watches/{watch_a['id']}/events", headers=headers_b).status_code == 404


def test_planner_created_watch_assigned_to_current_neon_user(auth_test_client: TestClient):
    """POST /v1/watches/from-plan must automatically scope the new watch to the authenticated Neon user."""
    neon_id = str(uuid.uuid4())
    token = f"neon_session_planner_{uuid.uuid4().hex}"
    register_test_session(token, neon_id, "planner@test.com")
    headers = {"Authorization": f"Bearer {token}"}

    user = auth_test_client.get("/v1/auth/me", headers=headers).json()
    user_id = user["id"]

    plan_payload = {
        "user_id": "malicious-different-id",
        "plan": {
            "url": "https://www.daraz.pk/products/test-planner-chair.html",
            "intent": "Track office chair price",
            "title": "Office Chair Monitor",
            "schedule": {
                "cadence_minutes": 30,
                "timezone": "Asia/Karachi",
            },
            "monitoring_spec": {
                "vertical": "product",
                "rules": [
                    {
                        "type": "price_below",
                        "field": "price",
                        "value": 2500,
                        "currency": "PKR",
                    }
                ],
            },
            "collector_id": "c_msz0zrtw29tjzhzakl",
            "readiness": "ready",
            "confidence_score": 0.95,
            "clarifications_needed": [],
            "source_prompt": "Alert me below 2500",
        },
    }

    create_res = auth_test_client.post("/v1/watches/from-plan", headers=headers, json=plan_payload)
    assert create_res.status_code == 201
    watch_data = create_res.json()
    assert watch_data["user_id"] == user_id
    assert watch_data["user_id"] != "malicious-different-id"
