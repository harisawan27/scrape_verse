import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import select

from app.models import User, Watch, WatchRun, Snapshot, Schedule, WatchTarget, Conversation, ConversationMessage, utc_now
from app.integrations.ai.types import (
    ProviderMetadata,
    SearchCandidate,
    DiscoveredWebResult,
    IntentClassification,
    ProviderRateLimitedError,
    ProviderQuotaExhaustedError,
)
from app.integrations.ai.groq_client import GroqAIClient
from app.integrations.ai.openrouter_client import OpenRouterSearchClient
from app.integrations.ai.official_ranker import OfficialSourceRanker
from app.integrations.ai.router import AIRouter
from app.services.rules import RuleEvaluator
from app.services.watch_actions import WatchActionHandler
from app.auth import get_optional_user, get_current_user
from app.main import app


@pytest.fixture
def auth_client(client):
    db = client.session_factory()
    user = db.scalar(select(User).where(User.email == "test_routing@webradar.local"))
    if not user:
        user = User(email="test_routing@webradar.local", auth_id="auth_routing_123")
        db.add(user)
        db.commit()
        db.refresh(user)

    app.dependency_overrides[get_optional_user] = lambda: user
    app.dependency_overrides[get_current_user] = lambda: user
    db.close()

    yield client, user

    app.dependency_overrides.pop(get_optional_user, None)
    app.dependency_overrides.pop(get_current_user, None)


def test_official_source_ranker_prioritizes_bau_over_aggregator():
    """Requirement 6: Ensure official bau.edu.tr domain is ranked ABOVE third-party aggregator academicjobs.com."""
    candidates = [
        SearchCandidate(url="https://www.academicjobs.com/bahcesehir-university-careers", title="Bahcesehir Jobs on AcademicJobs"),
        SearchCandidate(url="https://bau.edu.tr/kariyer-merkezi", title="Bahçeşehir Üniversitesi Kariyer Merkezi"),
        SearchCandidate(url="https://bau-hub.com/kariyer", title="BAU Hub"),
    ]
    ranked = OfficialSourceRanker.rank_candidates("Watch Bahçeşehir University for new jobs", candidates)
    assert len(ranked) == 3
    # First-party bau.edu.tr must be #1
    assert "bau.edu.tr" in ranked[0].url
    assert ranked[0].is_official is True
    # Aggregator must be demoted and not marked as official primary
    assert "academicjobs.com" in ranked[-1].url
    assert ranked[-1].priority_score < ranked[0].priority_score


def test_scenario_a_non_search_watch_chat(auth_client):
    """Test A: Non-search Watch Chat — 'Why haven't you alerted me yet?' calls Groq, NOT OpenRouter search."""
    import uuid
    client, user = auth_client
    watch_id = str(uuid.uuid4())

    with client.session_factory() as db:
        watch = Watch(
            id=watch_id,
            user_id=user.id,
            url="https://www.daraz.pk/products/-i519675927.html",
            title="Daraz Monitored Item",
            instruction="Alert when below PKR 800",
            monitoring_spec={"field": "price", "threshold": 800, "rules": [{"type": "price_below", "field": "price", "value": 800, "currency": "PKR"}]},
            status="active",
        )
        db.add(watch)
        run = WatchRun(watch_id=watch.id, scheduled_for=utc_now(), status="succeeded")
        db.add(run)
        db.commit()
        snapshot = Snapshot(
            run_id=run.id,
            watch_id=watch.id,
            payload={"price": 1099, "original_price": 2500, "on_sale": True, "currency": "PKR", "availability": "in stock"},
        )
        db.add(snapshot)
        db.commit()

    # Track OpenRouter search calls
    with patch.object(OpenRouterSearchClient, "discover_web") as mock_search:
        response = client.post(f"/v1/watches/{watch_id}/chat", json={"message": "Why haven't you alerted me yet?"})
        assert response.status_code == 200
        data = response.json()

        # OpenRouter search MUST NOT be called
        mock_search.assert_not_called()

        # Explanation must state live price 1,099 vs threshold 800
        assert "1,099" in data["reply"]
        assert "800" in data["reply"]


def test_scenario_b_natural_language_discovery_pipeline():
    """Test B: Natural language URL discovery — Groq classifies -> OpenRouter searches -> Official ranker -> Groq plans."""
    mock_groq = MagicMock(spec=GroqAIClient)
    mock_groq.default_model = "openai/gpt-oss-120b"
    mock_groq.classify_intent.return_value = IntentClassification(
        mode="WATCH",
        needs_web_search=True,
        explicit_url=None,
        entity_name="Bahçeşehir University",
    )
    mock_groq.synthesize_plan.return_value = (
        {
            "title": "Bahçeşehir University Careers Monitor",
            "content": "Monitoring Bahçeşehir University official career portal for new openings.",
            "primary_url": "https://bau.edu.tr/kariyer",
            "rules": [{"type": "availability_changed", "field": "status", "value": "updated"}],
            "cadence_minutes": 1440,
            "cadence_name": "daily",
        },
        ProviderMetadata(provider="groq", model="openai/gpt-oss-120b", used_web_search=False),
    )

    mock_openrouter = MagicMock(spec=OpenRouterSearchClient)
    mock_openrouter.is_configured.return_value = True
    mock_openrouter.discover_web.return_value = DiscoveredWebResult(
        raw_answer="Discovered official career portals for Bahçeşehir University.",
        candidates=[
            SearchCandidate(url="https://www.academicjobs.com/bahcesehir-university", title="AcademicJobs"),
            SearchCandidate(url="https://bau.edu.tr/kariyer", title="Bahçeşehir University HR"),
        ],
        metadata=ProviderMetadata(provider="openrouter", model="google/gemini-2.5-flash", used_web_search=True),
    )

    router = AIRouter(groq_client=mock_groq, openrouter_client=mock_openrouter)
    result = router.route_conversational_turn(message="Watch Bahçeşehir University for new jobs.")

    # 1. Groq classified intent
    mock_groq.classify_intent.assert_called_once()
    # 2. OpenRouter search was called
    mock_openrouter.discover_web.assert_called_once()
    # 3. OfficialSourceRanker prioritized bau.edu.tr
    assert len(result.sources) == 2
    assert "bau.edu.tr" in result.sources[0].url
    assert result.sources[0].official is True
    # 4. Result mode is WATCH
    assert result.mode == "WATCH"
    assert result.watch_url == "https://bau.edu.tr/kariyer"
    assert result.metadata["used_web_search"] is True


def test_scenario_c_explicit_url_skips_openrouter_search():
    """Test C: Explicit URL supplied — skips OpenRouter search to save quota."""
    mock_groq = MagicMock(spec=GroqAIClient)
    mock_groq.default_model = "openai/gpt-oss-120b"
    mock_groq.classify_intent.return_value = IntentClassification(
        mode="WATCH",
        needs_web_search=False,
        explicit_url="https://example.com/jobs",
    )
    mock_groq.synthesize_plan.return_value = (
        {
            "title": "Example Jobs Monitor",
            "content": "Monitoring https://example.com/jobs for changes.",
            "primary_url": "https://example.com/jobs",
            "rules": [{"type": "availability_changed", "field": "status", "value": "updated"}],
            "cadence_minutes": 1440,
            "cadence_name": "daily",
        },
        ProviderMetadata(provider="groq", model="openai/gpt-oss-120b", used_web_search=False),
    )

    mock_openrouter = MagicMock(spec=OpenRouterSearchClient)
    mock_openrouter.is_configured.return_value = True

    router = AIRouter(groq_client=mock_groq, openrouter_client=mock_openrouter)
    result = router.route_conversational_turn(message="Watch https://example.com/jobs for changes.")

    # OpenRouter search MUST NOT be called
    mock_openrouter.discover_web.assert_not_called()
    assert result.watch_url == "https://example.com/jobs"
    assert result.metadata["used_web_search"] is False


def test_scenario_d_ask_mode_creates_no_watch():
    """Test D: ASK mode — OpenRouter searches, Groq summarizes answer, NO watch created."""
    mock_groq = MagicMock(spec=GroqAIClient)
    mock_groq.default_model = "openai/gpt-oss-120b"
    mock_groq.classify_intent.return_value = IntentClassification(
        mode="ASK",
        needs_web_search=True,
        explicit_url=None,
    )
    mock_groq.synthesize_plan.return_value = (
        {
            "title": "Istanbul University Contact Info",
            "content": "Istanbul University Rectorate phone: +90 212 440 0000, website: https://istanbul.edu.tr",
            "primary_url": "https://istanbul.edu.tr",
            "rules": [],
        },
        ProviderMetadata(provider="groq", model="openai/gpt-oss-120b", used_web_search=False),
    )

    mock_openrouter = MagicMock(spec=OpenRouterSearchClient)
    mock_openrouter.is_configured.return_value = True
    mock_openrouter.discover_web.return_value = DiscoveredWebResult(
        raw_answer="Istanbul University contact info retrieved.",
        candidates=[SearchCandidate(url="https://istanbul.edu.tr", title="Istanbul University")],
        metadata=ProviderMetadata(provider="openrouter", model="google/gemini-2.5-flash", used_web_search=True),
    )

    router = AIRouter(groq_client=mock_groq, openrouter_client=mock_openrouter)
    result = router.route_conversational_turn(message="Find Istanbul University's official contact information.")

    assert result.mode == "ASK"
    assert result.watch_url is None  # NO watch URL for ASK mode
    assert len(result.sources) > 0
    assert "istanbul.edu.tr" in result.sources[0].url


def test_scenario_e_daraz_price_semantics_intact(auth_client):
    """Test E: Daraz selling-price semantics remain accurate (1099 current selling price vs 2500 original)."""
    watch = Watch(
        id="watch_eval_test",
        monitoring_spec={"rules": [{"type": "price_below", "field": "price", "value": 800, "currency": "PKR"}]},
    )
    curr_snapshot = {"price": 1099, "original_price": 2500, "on_sale": True, "currency": "PKR", "availability": "in_stock"}
    prev_snapshot = {"price": 2500, "original_price": 2500, "on_sale": False, "currency": "PKR", "availability": "in_stock"}

    events = RuleEvaluator.evaluate(watch, curr_snapshot, prev_snapshot)
    # Since 1099 is not below 800, price_below must not trigger
    below_events = [e for e in events if e.event_type == "price_below"]
    assert len(below_events) == 0


def test_scenario_f_scheduled_execution_uses_zero_llm_calls():
    """Test F: Scheduled monitoring scans use ZERO Groq and ZERO OpenRouter calls."""
    watch = Watch(
        id="watch_zero_llm",
        monitoring_spec={"rules": [{"type": "price_below", "field": "price", "value": 1200, "currency": "PKR"}]},
    )
    curr_snapshot = {"price": 1099, "original_price": 2500, "currency": "PKR", "availability": "in_stock"}

    prev_snapshot = {"price": 2500, "original_price": 2500, "currency": "PKR", "availability": "in_stock"}

    with patch.object(GroqAIClient, "_call_groq") as mock_groq_call, \
         patch.object(OpenRouterSearchClient, "discover_web") as mock_search_call:

        events = RuleEvaluator.evaluate(watch, curr_snapshot, prev_snapshot)
        assert len(events) >= 1
        assert any(e.event_type == "price_threshold_crossed" for e in events)

        # Assert ZERO LLM calls were made
        mock_groq_call.assert_not_called()
        mock_search_call.assert_not_called()


def test_scenario_g_provider_exhaustion_handled_gracefully():
    """Test G: Quota exhaustion returns clean error without crashing or fabricating URLs."""
    mock_groq = MagicMock(spec=GroqAIClient)
    mock_groq.default_model = "openai/gpt-oss-120b"
    mock_groq.classify_intent.return_value = IntentClassification(
        mode="WATCH",
        needs_web_search=True,
        explicit_url=None,
    )

    mock_openrouter = MagicMock(spec=OpenRouterSearchClient)
    mock_openrouter.is_configured.return_value = True
    # Simulate OpenRouter 429 quota exhaustion
    mock_openrouter.discover_web.side_effect = ProviderQuotaExhaustedError("Credits exhausted", provider="openrouter")

    router = AIRouter(groq_client=mock_groq, openrouter_client=mock_openrouter)
    result = router.route_conversational_turn(message="Watch Istanbul University for scholarship updates.")

    # Must return helpful unavailable message rather than crashing or inventing URLs
    assert "temporarily unavailable" in result.content.lower()
    assert result.metadata.get("error") == "provider_quota_exhausted"
