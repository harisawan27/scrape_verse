import pytest
from sqlalchemy import select
from app.models import User, Watch, Schedule, WatchTarget, Conversation, ConversationMessage, Snapshot, WatchRun, utc_now
from app.auth import get_optional_user, get_current_user
from app.main import app


@pytest.fixture
def auth_client(client):
    db = client.session_factory()
    user = db.scalar(select(User).where(User.email == "test_phase8@webradar.local"))
    if not user:
        user = User(email="test_phase8@webradar.local", auth_id="auth_phase8_123")
        db.add(user)
        db.commit()
        db.refresh(user)

    app.dependency_overrides[get_optional_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user
    db.close()

    yield client, user

    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_scenario_a_ask_mode(auth_client):
    """Scenario A: ASK mode — Finds contact info, cites official sources, creates NO watch."""
    client, user = auth_client

    payload = {
        "message": "Find Istanbul University's official contact information."
    }
    response = client.post("/v1/conversations", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "ASK"
    assert data["message_type"] == "answer"
    assert "iro@istanbul.edu.tr" in data["content"] or "Istanbul University" in data["content"]
    assert len(data["sources"]) > 0
    assert any("istanbul.edu.tr" in s["url"] for s in data["sources"])
    assert data["watch"] is None

    # Verify no watch was created in DB for this prompt
    with client.session_factory() as db:
        watches = db.scalars(select(Watch).where(Watch.user_id == user.id)).all()
        assert len(watches) == 0

        # Verify conversation was recorded
        conv = db.get(Conversation, data["conversation_id"])
        assert conv is not None
        assert len(conv.messages) == 2  # user + assistant


def test_scenario_b_watch_without_url(auth_client):
    """Scenario B: WATCH WITHOUT URL — Discovers official careers portal, creates persistent Watch + targets + schedule."""
    client, user = auth_client

    payload = {
        "message": "Watch Bahçeşehir University for new jobs."
    }
    response = client.post("/v1/conversations", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "WATCH"
    assert data["message_type"] == "watch_created"
    assert data["watch"] is not None
    assert "Bahçeşehir" in data["watch"]["title"] or "Bahcesehir" in data["watch"]["title"]
    assert "bau.edu.tr" in data["watch"]["url"]

    # Verify watch in Neon/test DB
    watch_id = data["watch"]["id"]
    with client.session_factory() as db:
        db_watch = db.get(Watch, watch_id)
        assert db_watch is not None
        assert db_watch.status == "active"
        assert db_watch.schedule is not None
        assert len(db_watch.targets) > 0
        assert any("bau.edu.tr" in t.url for t in db_watch.targets)


def test_scenario_c_ask_and_watch(auth_client):
    """Scenario C: ASK_AND_WATCH — Answers current status now AND creates persistent Watch."""
    client, user = auth_client

    payload = {
        "message": "Check Istanbul University's bachelor's scholarship information and tell me when applications open."
    }
    response = client.post("/v1/conversations", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "ASK_AND_WATCH"
    assert data["message_type"] == "scan_result"
    assert "not currently open" in data["content"].lower() or "scholarship" in data["content"].lower()
    assert data["watch"] is not None
    assert "Scholarship" in data["watch"]["title"]
    assert len(data["sources"]) > 0

    # Verify watch and targets in DB
    watch_id = data["watch"]["id"]
    with client.session_factory() as db:
        db_watch = db.get(Watch, watch_id)
        assert db_watch is not None
        assert db_watch.schedule is not None
        assert len(db_watch.targets) >= 2


def test_scenario_d_watch_chat_and_action_execution(auth_client):
    """Scenario D: WATCH CHAT & ACTIONS — Explains status & executes threshold update action."""
    client, user = auth_client

    # 1. Setup a Daraz Watch in DB with price=1099 and threshold=800
    with client.session_factory() as db:
        watch = Watch(
            user_id=user.id,
            url="https://www.daraz.pk/products/-i519675927-s3479476860.html",
            title="Daraz Monitored Toy Gun",
            instruction="Alert when price drops below PKR 800",
            monitoring_spec={
                "field": "price",
                "threshold": 800,
                "rules": [{"type": "price_below", "field": "price", "value": 800, "currency": "PKR"}],
            },
            status="active",
        )
        db.add(watch)
        db.commit()
        db.refresh(watch)

        run = WatchRun(watch_id=watch.id, scheduled_for=utc_now(), status="succeeded")
        db.add(run)
        db.commit()
        db.refresh(run)

        snapshot = Snapshot(
            run_id=run.id,
            watch_id=watch.id,
            payload={"price": 1099, "original_price": 2500, "on_sale": True, "currency": "PKR", "availability": "in stock"},
        )
        db.add(snapshot)
        db.commit()
        watch_id = watch.id

    # 2. Query: "Why haven't you alerted me yet?"
    chat_resp1 = client.post(f"/v1/watches/{watch_id}/chat", json={"message": "Why haven't you alerted me yet?"})
    assert chat_resp1.status_code == 200
    data1 = chat_resp1.json()
    assert "1,099" in data1["reply"]
    assert "800" in data1["reply"]
    assert data1["action_taken"] is None

    # 3. Action Command: "Change it to 1200."
    chat_resp2 = client.post(f"/v1/watches/{watch_id}/chat", json={"message": "Change it to 1200."})
    assert chat_resp2.status_code == 200
    data2 = chat_resp2.json()
    assert data2["action_taken"] == "rule_updated"
    assert "1,200" in data2["reply"]
    assert data2["action_details"]["new_threshold"] == 1200

    # 4. Verify DB was updated
    with client.session_factory() as db:
        updated_watch = db.get(Watch, watch_id)
        rules = updated_watch.monitoring_spec.get("rules", [])
        assert rules[0]["value"] == 1200


def test_scenario_e_ambiguity_and_clarification(auth_client):
    """Scenario E: Ambiguity Handling — Asks one concise clarification when institution is uncertain."""
    client, user = auth_client

    payload = {"message": "Watch BAU University for jobs."}
    response = client.post("/v1/conversations", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["mode"] == "CLARIFICATION"
    assert len(data["clarification_options"]) == 3
    assert any("Bahçeşehir" in opt or "Bahcesehir" in opt for opt in data["clarification_options"])
    assert any("Beirut" in opt for opt in data["clarification_options"])
    assert data["watch"] is None

    # Now reply with selected option
    reply_payload = {
        "conversation_id": data["conversation_id"],
        "message": "Watch Bahçeşehir University",
        "selected_option": "Bahçeşehir University (Istanbul, Türkiye)",
    }
    reply_resp = client.post("/v1/conversations", json=reply_payload)
    assert reply_resp.status_code == 200
    reply_data = reply_resp.json()
    assert reply_data["mode"] == "WATCH"
    assert reply_data["watch"] is not None
