import uuid
import pytest
from fastapi.testclient import TestClient

from app.db import get_session_factory
from app.integrations.llm import MockLLMPlannerClient, RawPlannerOutput, RawRule, RawSchedule
from app.main import app
from app.models import Watch
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchPlan, WatchPlanSchedule
from app.services.planner import (
    NaturalLanguageWatchPlanner,
    WatchPlanValidator,
    normalize_numeric_threshold,
    parse_natural_cadence,
    parse_natural_currency,
)


@pytest.fixture
def client():
    return TestClient(app)


def test_normalize_numeric_threshold():
    assert normalize_numeric_threshold(2500) == 2500.0
    assert normalize_numeric_threshold("2500") == 2500.0
    assert normalize_numeric_threshold("Rs 2,500") == 2500.0
    assert normalize_numeric_threshold("PKR 2,500.50") == 2500.50
    assert normalize_numeric_threshold("3k") == 3000.0
    assert normalize_numeric_threshold("2.5k") == 2500.0
    assert normalize_numeric_threshold("cheap") is None
    assert normalize_numeric_threshold(-50) is None


def test_parse_natural_cadence():
    assert parse_natural_cadence("every 30 minutes") == ("custom", 30)
    assert parse_natural_cadence("every 30m") == ("custom", 30)
    assert parse_natural_cadence("hourly") == ("hourly", 60)
    assert parse_natural_cadence("every hour") == ("hourly", 60)
    assert parse_natural_cadence("every 6 hours") == ("custom", 360)
    assert parse_natural_cadence("every 6h") == ("custom", 360)
    assert parse_natural_cadence("daily") == ("daily", 1440)
    assert parse_natural_cadence("every day") == ("daily", 1440)
    assert parse_natural_cadence("weekly") == ("weekly", 10080)


def test_planner_price_below_rs_2500():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/office-chair-i12345.html"
    res = planner.preview_plan(
        message="Watch this chair and alert me when it drops below Rs 2500",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    assert res.plan.url == url
    assert res.plan.collector_id == "c_msz0zrtw29tjzhzakl"
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "price_below"
    assert rule["value"] == 2500.0
    assert rule["currency"] == "PKR"


def test_planner_price_below_pkr_comma_format():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/earbuds-i67890.html"
    res = planner.preview_plan(
        message="Check every hour and notify if price < PKR 2,500",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    assert res.plan.schedule.cadence == "hourly"
    assert res.plan.schedule.cadence_minutes == 60
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "price_below"
    assert rule["value"] == 2500.0


def test_planner_price_below_3k_abbreviation():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/smartwatch-i99999.html"
    res = planner.preview_plan(
        message="Alert me below 3k",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "price_below"
    assert rule["value"] == 3000.0


def test_planner_price_above_5000():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/smartwatch-i99999.html"
    res = planner.preview_plan(
        message="Alert me when price exceeds Rs 5000",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "price_above"
    assert rule["value"] == 5000.0


def test_planner_generic_price_drop_rule():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/item-i111.html"
    res = planner.preview_plan(
        message="Tell me whenever the price drops",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "price_drop"
    assert rule["field"] == "price"


def test_planner_back_in_stock_rule():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/item-i111.html"
    res = planner.preview_plan(
        message="Notify me when this comes back in stock",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    rule = res.plan.monitoring_spec["rules"][0]
    assert rule["type"] == "back_in_stock"
    assert rule["field"] == "availability"


def test_planner_multiple_compatible_rules():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/item-i222.html"
    res = planner.preview_plan(
        message="Check this every 6 hours. Tell me if it drops below 3000 or comes back in stock.",
        url=url,
    )
    assert res.status == "ready"
    assert res.plan is not None
    assert res.plan.schedule.cadence_minutes == 360
    rule_types = [r["type"] for r in res.plan.monitoring_spec["rules"]]
    assert "price_below" in rule_types
    assert "back_in_stock" in rule_types


def test_planner_cadence_30_minutes_and_daily():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/item-i333.html"
    res_30m = planner.preview_plan(
        message="Check every 30 minutes and alert me below 1500",
        url=url,
    )
    assert res_30m.status == "ready"
    assert res_30m.plan.schedule.cadence_minutes == 30

    res_daily = planner.preview_plan(
        message="Check daily and alert me below 1500",
        url=url,
    )
    assert res_daily.status == "ready"
    assert res_daily.plan.schedule.cadence == "daily"
    assert res_daily.plan.schedule.cadence_minutes == 1440


def test_ambiguity_missing_numeric_threshold_requires_clarification():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    url = "https://www.daraz.pk/products/item-i444.html"
    res = planner.preview_plan(
        message="Alert me when it gets cheap",
        url=url,
    )
    assert res.status == "needs_clarification"
    assert "price_threshold" in res.missing
    assert res.clarification_prompt is not None
    assert res.plan is None


def test_ambiguity_missing_url_requires_clarification():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    res = planner.preview_plan(
        message="Watch this chair every hour and alert me below 2500",
        url=None,
    )
    assert res.status == "needs_clarification"
    assert "url" in res.missing
    assert res.clarification_prompt is not None
    assert res.plan is None


def test_unsupported_domain_rejected():
    planner = NaturalLanguageWatchPlanner(llm_client=MockLLMPlannerClient())
    res = planner.preview_plan(
        message="Watch this every 30 minutes and alert below $50",
        url="https://www.amazon.com/dp/B08N5WRWNW",
    )
    assert res.status == "unsupported"
    assert res.plan is None
    assert "amazon.com" in res.message


def test_model_supplied_collector_id_is_strictly_ignored():
    """Security: Model attempting to specify arbitrary collector ID is overridden by backend mapping."""
    class MaliciousModelClient:
        def generate_plan(self, *, user_message: str, url: str | None = None, default_timezone: str = "Asia/Karachi"):
            return RawPlannerOutput(
                url=url,
                vertical="product",
                intent="Injected collector test",
                schedule=RawSchedule(cadence_minutes=60, timezone=default_timezone),
                rules=[RawRule(type="price_below", value=2000, currency="PKR")],
                suggested_collector_id="c_attacker_evil_collector",
            )

    planner = NaturalLanguageWatchPlanner(
        llm_client=MaliciousModelClient(),
        validator=WatchPlanValidator(default_collector_id="c_msz0zrtw29tjzhzakl"),
    )
    res = planner.preview_plan(
        message="Track price",
        url="https://www.daraz.pk/products/item-i555.html",
    )
    assert res.status == "ready"
    assert res.plan is not None
    # Must match trusted backend configuration, NOT attacker-chosen collector
    assert res.plan.collector_id == "c_msz0zrtw29tjzhzakl"
    assert res.plan.monitoring_spec["collector_id"] == "c_msz0zrtw29tjzhzakl"


def test_unsupported_rule_types_filtered_out():
    """Validator removes unsupported/hallucinated rule types."""
    class HallucinatingModelClient:
        def generate_plan(self, *, user_message: str, url: str | None = None, default_timezone: str = "Asia/Karachi"):
            return RawPlannerOutput(
                url=url,
                vertical="product",
                intent="Hallucinated rules test",
                schedule=RawSchedule(cadence_minutes=60, timezone=default_timezone),
                rules=[
                    RawRule(type="unknown_hallucinated_rule", field="rating", value=4.5),
                    RawRule(type="price_below", field="price", value=1500, currency="PKR"),
                ],
            )

    planner = NaturalLanguageWatchPlanner(llm_client=HallucinatingModelClient())
    res = planner.preview_plan(
        message="Track product",
        url="https://www.daraz.pk/products/item-i666.html",
    )
    assert res.status == "ready"
    assert res.plan is not None
    assert len(res.plan.monitoring_spec["rules"]) == 1
    assert res.plan.monitoring_spec["rules"][0]["type"] == "price_below"


def test_api_watch_plan_preview_endpoint(client):
    """API test for POST /v1/watch-plans/preview."""
    payload = {
        "message": "Watch this Daraz chair every 30 minutes and alert me when it drops below Rs 2500.",
        "url": "https://www.daraz.pk/products/ergonomic-chair-i7777.html",
    }
    resp = client.post("/v1/watch-plans/preview", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ready"
    assert data["plan"]["url"] == "https://www.daraz.pk/products/ergonomic-chair-i7777.html"
    assert data["plan"]["schedule"]["cadence_minutes"] == 30
    assert data["plan"]["collector_id"] == "c_msz0zrtw29tjzhzakl"


def test_api_watch_create_from_plan_endpoint(client):
    """API test for POST /v1/watches/from-plan."""
    session_factory = get_session_factory()
    with session_factory() as db:
        user = WatchRepository(db).create_user(UserCreate(email=f"planner-{uuid.uuid4()}@example.com"))
        user_id = user.id

    plan_payload = {
        "url": "https://www.daraz.pk/products/wireless-earbuds-i8888.html",
        "title": "Wireless Earbuds",
        "vertical": "product",
        "intent": "Track price below 2000",
        "schedule": {
            "cadence": "hourly",
            "cadence_minutes": 60,
            "timezone": "Asia/Karachi",
        },
        "monitoring_spec": {
            "vertical": "product",
            "currency": "PKR",
            "collector_id": "c_msz0zrtw29tjzhzakl",
            "rules": [{"type": "price_below", "field": "price", "value": 2000, "currency": "PKR"}],
        },
        "collector_id": "c_msz0zrtw29tjzhzakl",
        "confidence": 1.0,
        "assumptions": ["Daraz product"],
    }

    resp = client.post("/v1/watches/from-plan", json={"user_id": user_id, "plan": plan_payload})
    assert resp.status_code == 201
    data = resp.json()
    assert data["id"] is not None
    assert data["user_id"] == user_id
    assert data["url"] == "https://www.daraz.pk/products/wireless-earbuds-i8888.html"
    assert data["status"] == "active"
    assert data["schedule"]["cadence"] == "hourly"
