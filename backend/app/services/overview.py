"""Domain services for deriving Watch health status, current product values,
and aggregate read models for frontend control surfaces.
"""

from typing import Any
from urllib.parse import urlparse

from app.models import Alert, ScraperRepair, Snapshot, Watch, WatchRun
from app.schemas import (
    ActivityEventRead,
    HealthStatus,
    ProductCurrentValue,
    WatchOverviewRead,
    WatchOverviewStats,
    WatchRead,
    WatchSummaryRead,
)


def extract_domain(url: str) -> str:
    """Extract clean domain/host from URL."""
    try:
        parsed = urlparse(url)
        host = parsed.netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host or url
    except Exception:
        return url


def derive_health_status(
    watch: Watch,
    runs: list[WatchRun],
    repairs: list[ScraperRepair] | None = None,
) -> HealthStatus:
    """Derive deterministic frontend health status in strict order of precedence:
    1. 'paused': Watch is not in 'active' status.
    2. 'repairing': An active repair (in_progress / pending) exists for this Watch.
    3. 'running': A WatchRun is currently active (running / pending).
    4. 'failed': The most recent completed/terminal run failed.
    5. 'healthy': The Watch is active with successful baseline runs or newly configured.
    """
    if watch.status != "active":
        return "paused"

    # Active repair check
    if repairs:
        for r in repairs:
            if r.status in ("pending", "in_progress"):
                return "repairing"

    # Active running / pending run check
    for run in runs:
        if run.status in ("running", "pending"):
            return "running"

    # Most recent run check
    if runs:
        # Sort runs by scheduled_for / created_at descending
        sorted_runs = sorted(runs, key=lambda r: r.scheduled_for or r.created_at, reverse=True)
        latest_run = sorted_runs[0]
        if latest_run.status == "failed":
            return "failed"
        if latest_run.status in ("succeeded", "success"):
            return "healthy"


    return "healthy"


def extract_product_current_value(snapshot: Snapshot | None) -> ProductCurrentValue | None:
    """Extract frontend-friendly current product state from the latest successful Snapshot."""
    if snapshot is None or not isinstance(snapshot.payload, dict):
        return None

    payload = snapshot.payload

    price = None
    raw_price = payload.get("price")
    if raw_price is not None:
        try:
            price = float(raw_price)
        except (ValueError, TypeError):
            price = None

    rating = None
    raw_rating = payload.get("rating")
    if raw_rating is not None:
        try:
            rating = float(raw_rating)
        except (ValueError, TypeError):
            rating = None

    reviews_count = None
    raw_reviews = payload.get("reviews_count")
    if raw_reviews is not None:
        try:
            reviews_count = int(raw_reviews)
        except (ValueError, TypeError):
            reviews_count = None

    return ProductCurrentValue(
        price=price,
        currency=payload.get("currency") or "PKR",
        availability=payload.get("availability"),
        title=payload.get("title"),
        seller=payload.get("seller"),
        rating=rating,
        reviews_count=reviews_count,
        extracted_at=snapshot.extracted_at or snapshot.captured_at or snapshot.created_at,
    )


def resolve_cadence_minutes(watch: Watch) -> int:
    """Derive cadence minutes from Schedule or monitoring_spec."""
    if not watch.schedule:
        return 60
    cadence = watch.schedule.cadence
    if cadence == "hourly":
        return 60
    if cadence == "daily":
        return 1440
    if cadence == "weekly":
        return 10080
    if cadence == "custom":
        spec_cadence = watch.monitoring_spec.get("cadence_minutes") if isinstance(watch.monitoring_spec, dict) else None
        if spec_cadence:
            try:
                return int(spec_cadence)
            except (ValueError, TypeError):
                pass
        return 60
    return 60
