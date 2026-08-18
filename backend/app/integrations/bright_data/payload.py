import re
from typing import Any


def parse_numeric_price(raw_price: Any) -> float | int | None:
    """Parse numeric price from string or number, stripping currency symbols and commas."""
    if raw_price is None:
        return None
    if isinstance(raw_price, (int, float)):
        return raw_price

    text = str(raw_price).strip().replace(",", "")
    match = re.search(r"(\d+(?:\.\d+)?)", text)
    if match:
        val_str = match.group(1)
        return float(val_str) if "." in val_str else int(val_str)
    return None


def map_bright_data_to_snapshot(
    raw_data: list[dict[str, Any]] | dict[str, Any] | None,
    *,
    default_url: str = "",
    default_title: str = "",
) -> dict[str, Any]:
    """Convert raw Bright Data Scraper Studio output into a validated structured snapshot payload."""
    if not raw_data:
        return {
            "url": default_url,
            "title": default_title,
            "price": None,
            "currency": None,
            "availability": "unknown",
            "extracted_fields": {},
        }

    # Normalize to a single item dictionary
    item: dict[str, Any]
    if isinstance(raw_data, list):
        item = raw_data[0] if raw_data else {}
    elif isinstance(raw_data, dict):
        item = raw_data
    else:
        item = {}

    url = item.get("url") or item.get("link") or item.get("product_url") or default_url
    title = item.get("title") or item.get("name") or item.get("product_title") or default_title

    # Price resolution
    raw_price = (
        item.get("price")
        or item.get("final_price")
        or item.get("current_price")
        or item.get("sale_price")
    )
    price = parse_numeric_price(raw_price)

    currency = (
        item.get("currency")
        or item.get("currency_symbol")
        or item.get("price_currency")
    )

    availability = (
        item.get("availability")
        or item.get("stock_status")
        or item.get("in_stock")
        or ("in_stock" if price is not None else "unknown")
    )

    # Preserve all other extracted properties in extracted_fields
    known_keys = {"url", "link", "product_url", "title", "name", "product_title", "price", "final_price", "current_price", "sale_price", "currency", "currency_symbol", "price_currency", "availability", "stock_status", "in_stock"}
    extra_fields = {k: v for k, v in item.items() if k not in known_keys}

    return {
        "url": str(url),
        "title": str(title),
        "price": price,
        "currency": str(currency) if currency else None,
        "availability": str(availability),
        "extracted_fields": extra_fields,
    }
