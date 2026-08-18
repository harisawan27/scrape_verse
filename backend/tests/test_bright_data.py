import os
import uuid
import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.integrations.bright_data import (
    BrightDataAuthError,
    BrightDataNotFoundError,
    BrightDataRateLimitError,
    CollectionProgress,
    CollectionTriggerResult,
    HttpBrightDataAdapter,
    MockBrightDataAdapter,
    map_bright_data_to_snapshot,
    parse_numeric_price,
)
from app.models import Base, WatchRun
from app.repositories import WatchRepository
from app.schemas import UserCreate, WatchCreate
from app.services.runs import RunCreationService


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


def test_auth_headers_and_error_handling():
    def custom_handler(request: httpx.Request) -> httpx.Response:
        auth = request.headers.get("Authorization")
        if auth != "Bearer valid-test-key":
            return httpx.Response(401, json={"error": "Unauthorized"})
        return httpx.Response(200, json={"snapshot_id": "s_12345", "status": "running"})

    transport = httpx.MockTransport(custom_handler)
    client = httpx.Client(transport=transport)

    # 1. Invalid key raises BrightDataAuthError
    invalid_adapter = HttpBrightDataAdapter(api_key="wrong-key", http_client=client)
    with pytest.raises(BrightDataAuthError):
        invalid_adapter.trigger_collection(collector_id="c_test", inputs=[{"url": "https://example.com"}])

    # 2. Valid key passes Authorization header and returns snapshot_id
    valid_adapter = HttpBrightDataAdapter(api_key="valid-test-key", http_client=client)
    result = valid_adapter.trigger_collection(collector_id="c_test", inputs=[{"url": "https://example.com"}])
    assert isinstance(result, CollectionTriggerResult)
    assert result.collection_id == "s_12345"
    assert result.status == "running"


def test_collection_trigger_and_parameter_structure():
    captured_requests = []

    def mock_trigger(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        return httpx.Response(200, json={"response_id": "s_collect_99", "status": "running"})

    transport = httpx.MockTransport(mock_trigger)
    client = httpx.Client(transport=transport)
    adapter = HttpBrightDataAdapter(api_key="secret-key", http_client=client)

    # 1. Scraper Studio (c_...) routes to /dca/trigger
    inputs = [{"url": "https://example.com/item/1"}]
    res = adapter.trigger_collection(
        collector_id="c_product_scraper",
        inputs=inputs,
        webhook_url="https://our-api.com/v1/webhooks/brightdata",
    )
    assert res.collection_id == "s_collect_99"
    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.url.path == "/dca/trigger"
    assert req.url.params.get("collector") == "c_product_scraper"
    assert req.url.params.get("endpoint") == "https://our-api.com/v1/webhooks/brightdata"

    # 2. Datasets v3 (gd_...) routes to /datasets/v3/trigger
    res_v3 = adapter.trigger_collection(
        collector_id="gd_product_dataset",
        inputs=inputs,
    )
    assert len(captured_requests) == 2
    req_v3 = captured_requests[1]
    assert req_v3.url.path == "/datasets/v3/trigger"
    assert req_v3.url.params.get("dataset_id") == "gd_product_dataset"


def test_collection_progress_status_polling():
    states = [
        {"status": "running", "progress": 0.3},
        {"status": "done", "lines": 1, "fails": 0},
        {"status": "done", "lines": 0, "fails": 1},
    ]

    def mock_progress(request: httpx.Request) -> httpx.Response:
        state = states.pop(0)
        return httpx.Response(200, json=state)

    transport = httpx.MockTransport(mock_progress)
    client = httpx.Client(transport=transport)
    adapter = HttpBrightDataAdapter(api_key="secret-key", http_client=client)

    # 1. Running state
    p1 = adapter.get_collection_status(collection_id="s_101")
    assert p1.status == "running"
    assert not p1.is_ready
    assert not p1.is_failed

    # 2. Ready state (done with lines > 0)
    p2 = adapter.get_collection_status(collection_id="s_101")
    assert p2.status == "ready"
    assert p2.is_ready

    # 3. Failed state (done with fails > 0 and 0 lines)
    p3 = adapter.get_collection_status(collection_id="s_101")
    assert p3.status == "failed"
    assert p3.is_failed


def test_collection_result_download():
    def mock_download(request: httpx.Request) -> httpx.Response:
        if "not_ready" in str(request.url):
            return httpx.Response(202, text="Processing")
        return httpx.Response(
            200,
            json=[{"url": "https://example.com/product", "title": "Desk Lamp", "price": 1499.50, "currency": "PKR"}],
        )

    transport = httpx.MockTransport(mock_download)
    client = httpx.Client(transport=transport)
    adapter = HttpBrightDataAdapter(api_key="secret-key", http_client=client)

    assert adapter.get_collection_result(collection_id="not_ready", max_retries=1) is None
    data = adapter.get_collection_result(collection_id="s_ready_102")
    assert data is not None
    assert len(data) == 1
    assert data[0]["title"] == "Desk Lamp"


def test_error_status_codes():
    def error_router(request: httpx.Request) -> httpx.Response:
        if "rate_limit" in str(request.url):
            return httpx.Response(429, json={"error": "Rate limit exceeded"})
        if "not_found" in str(request.url):
            return httpx.Response(404, json={"error": "Resource not found"})
        return httpx.Response(500, text="Internal Server Error")

    transport = httpx.MockTransport(error_router)
    client = httpx.Client(transport=transport)
    adapter = HttpBrightDataAdapter(api_key="secret-key", http_client=client)

    with pytest.raises(BrightDataRateLimitError):
        adapter.trigger_collection(collector_id="rate_limit", inputs=[{"url": "https://example.com"}])

    with pytest.raises(BrightDataNotFoundError):
        adapter.trigger_collection(collector_id="not_found", inputs=[{"url": "https://example.com"}])



def test_price_parser_and_payload_normalizer():
    assert parse_numeric_price("PKR 2,499.00") == 2499.0
    assert parse_numeric_price("USD $19.99") == 19.99
    assert parse_numeric_price("2500") == 2500
    assert parse_numeric_price(3200) == 3200
    assert parse_numeric_price("Out of stock") is None

    raw_scraper_output = [
        {
            "product_url": "https://example.com/chair",
            "product_title": "Executive Ergonomic Office Chair",
            "sale_price": "Rs. 15,500.00",
            "currency": "PKR",
            "stock_status": "in_stock",
            "seller": "FurnitureStorePK",
            "rating": 4.8,
        }
    ]

    snapshot_payload = map_bright_data_to_snapshot(
        raw_scraper_output,
        default_url="https://example.com/chair",
        default_title="Office Chair",
    )

    assert snapshot_payload["url"] == "https://example.com/chair"
    assert snapshot_payload["title"] == "Executive Ergonomic Office Chair"
    assert snapshot_payload["price"] == 15500.0
    assert snapshot_payload["currency"] == "PKR"
    assert snapshot_payload["availability"] == "in_stock"
    assert snapshot_payload["extracted_fields"]["seller"] == "FurnitureStorePK"
    assert snapshot_payload["extracted_fields"]["rating"] == 4.8


def test_watch_run_correlation_with_bright_data_collection_id(db):
    """Verify storing Bright Data collection/snapshot ID on WatchRun for correlation."""
    repository = WatchRepository(db)
    user = repository.create_user(UserCreate(email=f"bd-{uuid.uuid4()}@example.com"))
    watch = repository.create(
        WatchCreate.model_validate(
            {
                "user_id": user.id,
                "url": "https://example.com/product",
                "title": "BD Correlated Product",
                "instruction": "Alert when price < 2500",
                "monitoring_spec": {"field": "price", "value": 2500},
                "schedule": {
                    "cadence": "daily",
                    "timezone": "UTC",
                    "next_due_at": "2026-08-18T09:00:00+00:00",
                },
            }
        )
    )

    run = RunCreationService(db).create(watch.id)
    assert run.status == "pending"

    # Simulate triggering collection via adapter
    mock_adapter = MockBrightDataAdapter(preset_collection_id="s_bd_job_7788")
    result = mock_adapter.trigger_collection(
        collector_id="c_product_collector",
        inputs=[{"url": watch.url}],
    )

    # Persist the correlation ID on the WatchRun
    run.bright_data_collection_id = result.collection_id
    run.status = "running"
    db.commit()

    # Re-fetch from DB to verify correlation persistence
    persisted_run = db.get(WatchRun, run.id)
    assert persisted_run is not None
    assert persisted_run.bright_data_collection_id == "s_bd_job_7788"
    assert persisted_run.status == "running"


@pytest.mark.bright_data
def test_live_bright_data_credentials_validation():
    """Live integration test against real Bright Data API when credentials exist in .env."""
    settings = get_settings()
    api_key = settings.bright_data_api_key or os.getenv("BRIGHTDATA_API_KEY") or os.getenv("BRIGHT_DATA_API_KEY")
    collector_id = settings.bright_data_collector_id or os.getenv("BRIGHTDATA_COLLECTOR_ID") or os.getenv("BRIGHT_DATA_COLLECTOR_ID")

    if not api_key:
        pytest.skip("Set BRIGHTDATA_API_KEY in .env to run live Bright Data validation")

    adapter = HttpBrightDataAdapter(api_key=api_key, base_url=settings.bright_data_base_url)

    if collector_id:
        # Trigger real collection against Daraz product URL
        trigger_res = adapter.trigger_collection(
            collector_id=collector_id,
            inputs=[{"url": "https://www.daraz.pk/products/m10-tws-wireless-bluetooth-earbuds-touch-control-waterproof-headsets-with-microphone-i435345719.html"}],
        )
        assert trigger_res.collection_id is not None
        assert trigger_res.status in {"running", "pending"}

        # Check status
        status_res = adapter.get_collection_status(collection_id=trigger_res.collection_id)
        assert status_res.status in {"pending", "running", "ready"}

