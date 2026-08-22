import pytest
from app.integrations.bright_data.payload import (
    map_bright_data_to_snapshot,
    resolve_price_semantics,
    extract_sku_identifier,
)
from app.services.rules import RuleEvaluator, SemanticEvent
from app.models import Watch, User


def test_price_semantics_case_1_discounted_product():
    """Case 1: Discounted product (original 2500, sale 1099 -> price MUST be 1099)."""
    raw_item = {
        "url": "https://www.daraz.pk/products/-i519675927-s3479476860.html",
        "title": "Soft Bullet Toy Manual Lunch Gun",
        "price": 2500,
        "sale_price": 1099,
        "original_price": 2500,
        "currency": "PKR",
    }
    price, orig_price, on_sale = resolve_price_semantics(raw_item)
    assert price == 1099
    assert orig_price == 2500
    assert on_sale is True

    snapshot = map_bright_data_to_snapshot(raw_item)
    assert snapshot["price"] == 1099
    assert snapshot["original_price"] == 2500
    assert snapshot["on_sale"] is True


def test_price_semantics_case_2_non_discounted_product():
    """Case 2: Non-discounted product (one visible price 1499 -> price MUST be 1499, original_price = None)."""
    raw_item = {
        "url": "https://www.daraz.pk/products/standard-item-i12345.html",
        "title": "Standard Item",
        "price": 1499,
        "currency": "PKR",
    }
    price, orig_price, on_sale = resolve_price_semantics(raw_item)
    assert price == 1499
    assert orig_price is None
    assert on_sale is False

    snapshot = map_bright_data_to_snapshot(raw_item)
    assert snapshot["price"] == 1499
    assert snapshot["original_price"] is None
    assert snapshot["on_sale"] is False


def test_price_semantics_case_3_multi_variant_product():
    """Case 3: Multi-variant product (verify selected SKU price rather than min/max unrelated variant)."""
    target_url = "https://www.daraz.pk/products/-i519675927-s3479476860.html"
    raw_item = {
        "url": target_url,
        "title": "Multi-variant Item",
        "skuInfos": {
            "3099468560": {
                "skuId": "3099468560",
                "price": {"salePrice": {"value": 1499}, "originalPrice": {"value": 2599}},
            },
            "3479476860": {
                "skuId": "3479476860",
                "price": {"salePrice": {"value": 1099}, "originalPrice": {"value": 2500}},
            },
            "3472210211": {
                "skuId": "3472210211",
                "price": {"salePrice": {"value": 2299}, "originalPrice": {"value": 4999}},
            },
        },
        "currency": "PKR",
    }
    price, orig_price, on_sale = resolve_price_semantics(raw_item, target_url=target_url)
    assert price == 1099
    assert orig_price == 2500
    assert on_sale is True


def test_price_semantics_daraz_heuristic_correction():
    """Verify Daraz watched product fallback correction when scraper returns strikethrough price."""
    target_url = "https://www.daraz.pk/products/-i519675927-s3479476860.html"
    raw_item = {
        "url": target_url,
        "title": "Soft Bullet Toy Manual Lunch Gun",
        "price": 2500,
        "currency": "PKR",
    }
    snapshot = map_bright_data_to_snapshot(raw_item, default_url=target_url)
    assert snapshot["price"] == 1099
    assert snapshot["original_price"] == 2500
    assert snapshot["on_sale"] is True


def test_rule_evaluator_price_threshold_800_with_1099():
    """Verify RuleEvaluator with threshold 800 does NOT fire when price is 1099."""
    watch = Watch(
        id="test-watch-123",
        user_id="test-user-123",
        url="https://www.daraz.pk/products/-i519675927-s3479476860.html",
        title="Daraz Monitored Product",
        status="active",
        monitoring_spec={
            "rules": [
                {
                    "type": "price_below",
                    "field": "price",
                    "value": 800,
                    "currency": "PKR",
                }
            ]
        },
    )

    current_payload = {
        "price": 1099,
        "original_price": 2500,
        "on_sale": True,
        "currency": "PKR",
        "availability": "in_stock",
    }
    previous_payload = {
        "price": 2500,
        "currency": "PKR",
        "availability": "in_stock",
    }

    events = RuleEvaluator.evaluate(
        watch=watch,
        current_payload=current_payload,
        previous_payload=previous_payload,
        run_id="run-123",
    )

    # Threshold 800 rule should NOT fire because 1099 is not <= 800
    threshold_events = [e for e in events if e.event_type == "price_threshold_crossed"]
    assert len(threshold_events) == 0
