"""Scraper Studio self-healing and automated repair lifecycle.

Handles schema/extraction failure detection, repair prompt generation,
and repair progress orchestration.
"""

from datetime import datetime, timezone
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.bright_data.client import (
    BrightDataAdapter,
    HttpBrightDataAdapter,
    MockBrightDataAdapter,
)
from app.models import ScraperRepair, Watch, WatchRun

logger = logging.getLogger(__name__)

ACTIVE_REPAIR_STATES = {"pending", "in_progress", "pending_answer", "requires_manual_promotion"}
EXPECTED_PRODUCT_FIELDS = [
    "url",
    "title",
    "price",
    "currency",
    "availability",
    "seller",
    "rating",
    "reviews_count",
]


def validate_product_payload(payload: dict[str, Any] | None) -> tuple[bool, list[str]]:
    """Validate that extraction payload conforms to product schema.

    Returns (is_valid, list_of_missing_or_invalid_fields).
    """
    if not payload or not isinstance(payload, dict):
        return False, ["empty_payload"]

    missing: list[str] = []

    # Required fields
    if not payload.get("url"):
        missing.append("url")
    if not payload.get("title"):
        missing.append("title")
    if not payload.get("currency"):
        missing.append("currency")

    # Price validation: price = null is an extraction failure for product monitoring
    price_val = payload.get("price")
    if price_val is None:
        missing.append("price")
    elif isinstance(price_val, (int, float)):
        if price_val <= 0:
            missing.append("price")
    elif isinstance(price_val, str):
        cleaned = price_val.strip().replace(",", "")
        for prefix in ("PKR", "USD", "EUR", "GBP", "Rs.", "Rs", "$"):
            if cleaned.upper().startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
        try:
            val = float(cleaned)
            if val <= 0:
                missing.append("price")
        except ValueError:
            missing.append("price")
    else:
        missing.append("price")

    return len(missing) == 0, missing


def generate_repair_prompt(
    collector_id: str,
    target_url: str,
    missing_fields: list[str],
    expected_fields: list[str] | None = None,
) -> str:
    """Generate a deterministic repair prompt without LLM tokens."""
    expected = expected_fields or EXPECTED_PRODUCT_FIELDS
    missing_str = ", ".join(missing_fields)
    expected_str = ", ".join(expected)
    return (
        f"The scraper previously extracted {expected_str}. "
        f"The current execution for target URL '{target_url}' failed to extract valid required fields: {missing_str}. "
        f"Repair the scraper extraction selectors/logic so that all fields ({expected_str}) are correctly extracted "
        f"while strictly preserving the structured output schema."
    )


class SelfHealingService:
    """Orchestrates detection, repair submission, and verification of Scraper Studio collectors."""

    def __init__(self, db: Session, adapter: BrightDataAdapter | None = None):
        from app.config import get_settings

        self.db = db
        settings = get_settings()
        if adapter is not None:
            self.adapter = adapter
        elif settings.bright_data_api_key:
            self.adapter = HttpBrightDataAdapter(
                api_key=settings.bright_data_api_key,
                base_url=settings.bright_data_base_url,
            )
        else:
            self.adapter = MockBrightDataAdapter()

    def get_active_repair_for_run(self, run_id: str) -> ScraperRepair | None:
        statement = select(ScraperRepair).where(
            ScraperRepair.run_id == run_id,
            ScraperRepair.status.in_(ACTIVE_REPAIR_STATES),
        )
        return self.db.scalar(statement)

    def trigger_repair_for_run(
        self,
        watch: Watch,
        run: WatchRun,
        collector_id: str,
        missing_fields: list[str],
    ) -> ScraperRepair:
        """Create a durable repair attempt for an extraction failure if none exists."""
        existing = self.get_active_repair_for_run(run.id)
        if existing is not None:
            return existing

        prompt = generate_repair_prompt(
            collector_id=collector_id,
            target_url=watch.url,
            missing_fields=missing_fields,
        )

        repair = ScraperRepair(
            watch_id=watch.id,
            run_id=run.id,
            collector_id=collector_id,
            repair_prompt=prompt,
            missing_fields=missing_fields,
            status="pending",
        )
        self.db.add(repair)
        self.db.commit()
        self.db.refresh(repair)

        # Trigger refactor on Bright Data immediately
        try:
            res = self.adapter.trigger_refactor(
                collector_id=collector_id,
                prompt=prompt,
            )
            repair.refactor_job_id = res.job_id
            repair.status = "in_progress"
            self.db.commit()
            self.db.refresh(repair)
        except Exception as exc:
            repair.status = "failed"
            repair.failure_reason = f"Refactor trigger failed: {exc}"
            self.db.commit()
            self.db.refresh(repair)

        return repair

    def poll_active_repairs(self) -> list[ScraperRepair]:
        """Poll in-flight repairs and transition states."""
        statement = select(ScraperRepair).where(
            ScraperRepair.status.in_(["pending", "in_progress", "pending_answer"])
        )
        active_repairs = list(self.db.scalars(statement).all())
        updated: list[ScraperRepair] = []

        for repair in active_repairs:
            if repair.status == "pending":
                try:
                    res = self.adapter.trigger_refactor(
                        collector_id=repair.collector_id,
                        prompt=repair.repair_prompt,
                    )
                    repair.refactor_job_id = res.job_id
                    repair.status = "in_progress"
                    self.db.commit()
                    updated.append(repair)
                except Exception as exc:
                    repair.status = "failed"
                    repair.failure_reason = str(exc)
                    self.db.commit()
                    updated.append(repair)

            elif repair.status in {"in_progress", "pending_answer"}:
                try:
                    status_res = self.adapter.get_refactor_status(collector_id=repair.collector_id)
                except Exception as exc:
                    logger.warning("Failed to poll refactor status for %s: %s", repair.collector_id, exc)
                    continue

                if status_res.is_failed:
                    repair.status = "failed"
                    repair.failure_reason = status_res.error or "Bright Data refactor reported failure"
                    self.db.commit()
                    updated.append(repair)
                elif status_res.requires_approval or status_res.status == "pending_answer":
                    # Attempt automated approval / promotion if supported
                    approved = self.adapter.approve_refactor(collector_id=repair.collector_id)
                    if approved:
                        repair.status = "applied"
                    else:
                        repair.status = "requires_manual_promotion"
                    self.db.commit()
                    updated.append(repair)
                elif status_res.is_ready:
                    repair.status = "ready"
                    self.db.commit()
                    updated.append(repair)

        return updated
