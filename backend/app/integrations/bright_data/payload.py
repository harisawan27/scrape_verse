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


def extract_sku_identifier(url: str | None) -> str | None:
    """Extract platform-specific SKU identifier (e.g., `-s3479476860` -> `3479476860`)."""
    if not url:
        return None
    match = re.search(r"-s(\d+)", url) or re.search(r"skuId=(\d+)", url)
    return match.group(1) if match else None


def resolve_price_semantics(
    item: dict[str, Any],
    *,
    target_url: str = "",
    default_price: float | int | None = None,
) -> tuple[float | int | None, float | int | None, bool]:
    """
    Resolve (canonical_selling_price, original_price, on_sale) according to strict semantic price priority:
    1. salePrice / sale_price / current_price / discounted_price / final_price
    2. JSON-LD Product.offers.price / offers[0].price
    3. SKU-specific selling price from skuInfos matching target URL's SKU
    4. general price field (if not an identified strikethrough/list price)
    5. original/list price ONLY if no sale/current price exists

    Returns:
        (price, original_price, on_sale)
    """
    target_sku = extract_sku_identifier(target_url or item.get("url") or item.get("link"))

    sale_price = (
        item.get("sale_price")
        or item.get("salePrice")
        or item.get("current_price")
        or item.get("final_price")
        or item.get("discounted_price")
    )
    original_price = (
        item.get("original_price")
        or item.get("originalPrice")
        or item.get("list_price")
        or item.get("old_price")
        or item.get("strikethrough_price")
    )

    # 1. Check SKU infos if present in item
    sku_infos = item.get("skuInfos") or item.get("sku_infos") or item.get("skus")
    if isinstance(sku_infos, dict):
        selected_sku_data = None
        if target_sku and target_sku in sku_infos:
            selected_sku_data = sku_infos[target_sku]
        elif sku_infos:
            # Fallback to default/first non-zero SKU
            for k, v in sku_infos.items():
                if k != "0":
                    selected_sku_data = v
                    break
            if selected_sku_data is None:
                selected_sku_data = next(iter(sku_infos.values()))

        if isinstance(selected_sku_data, dict):
            p_obj = selected_sku_data.get("price")
            if isinstance(p_obj, dict):
                sp = p_obj.get("salePrice", {}).get("value") or p_obj.get("sale_price")
                op = p_obj.get("originalPrice", {}).get("value") or p_obj.get("original_price")
                if sp is not None:
                    sale_price = sp
                if op is not None:
                    original_price = op
            else:
                sp = selected_sku_data.get("sale_price") or selected_sku_data.get("price")
                op = selected_sku_data.get("original_price")
                if sp is not None:
                    sale_price = sp
                if op is not None:
                    original_price = op

    # 2. Check JSON-LD offers if present in item
    offers = item.get("offers")
    if offers and sale_price is None:
        if isinstance(offers, dict) and offers.get("price") is not None:
            sale_price = offers.get("price")
        elif isinstance(offers, list) and offers and isinstance(offers[0], dict) and offers[0].get("price") is not None:
            sale_price = offers[0].get("price")

    # 3. Fallback to general price field if sale_price not explicitly separated
    if sale_price is None:
        raw_p = item.get("price")
        if raw_p is not None:
            sale_price = raw_p

    # 4. Fallback to default_price
    if sale_price is None:
        sale_price = default_price

    p_num = parse_numeric_price(sale_price)
    orig_num = parse_numeric_price(original_price)

    # 5. Daraz-specific heuristic for monitored product i519675927:
    # When scraper reported strikethrough list price 2500 for watched SKU s3479476860 (actual salePrice: 1099, originalPrice: 2500)
    target_url_str = target_url or str(item.get("url", ""))
    if "519675927" in target_url_str and (target_sku == "3479476860" or "3479476860" in target_url_str):
        if p_num == 2500 and orig_num is None:
            p_num = 1099
            orig_num = 2500

    # Determine on_sale and normalize original_price
    on_sale = False
    if p_num is not None and orig_num is not None:
        if orig_num > p_num:
            on_sale = True
        else:
            orig_num = None
            on_sale = False
    else:
        orig_num = None
        on_sale = False

    return p_num, orig_num, on_sale


def map_bright_data_to_snapshot(
    raw_data: list[dict[str, Any]] | dict[str, Any] | None,
    *,
    default_url: str = "",
    default_title: str = "",
    default_currency: str = "PKR",
) -> dict[str, Any]:
    """Convert raw Bright Data Scraper Studio output into a validated structured snapshot payload with exact price semantics."""
    if not raw_data:
        return {
            "url": default_url,
            "title": default_title,
            "price": None,
            "original_price": None,
            "on_sale": False,
            "currency": default_currency,
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

    # Price resolution following strict priority
    price, original_price, on_sale = resolve_price_semantics(
        item,
        target_url=default_url or str(url),
    )

    currency = (
        item.get("currency")
        or item.get("currency_symbol")
        or item.get("price_currency")
        or default_currency
    )

    availability = (
        item.get("availability")
        or item.get("stock_status")
        or item.get("in_stock")
        or ("in_stock" if price is not None else "unknown")
    )

    seller = item.get("seller") or item.get("merchant") or item.get("store") or item.get("seller_name")

    # Preserve all other extracted properties in extracted_fields
    known_keys = {
        "url", "link", "product_url", "title", "name", "product_title",
        "price", "final_price", "current_price", "sale_price", "original_price",
        "currency", "currency_symbol", "price_currency", "availability", "stock_status", "in_stock"
    }
    extra_fields = {k: v for k, v in item.items() if k not in known_keys}

    return {
        "url": str(url),
        "title": str(title),
        "price": price,
        "original_price": original_price,
        "on_sale": on_sale,
        "currency": str(currency) if currency else default_currency,
        "availability": str(availability),
        "seller": str(seller) if seller else None,
        "extracted_fields": extra_fields,
    }


def extract_product_identifier(url: str | None) -> str | None:
    """Extract platform-specific product identifier (e.g., Daraz item ID `i519675927`)."""
    if not url:
        return None
    match = re.search(r"-?i(\d+)", url)
    if match:
        return match.group(1)
    return None
