import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.config import get_settings
from app.integrations.llm import (
    GeminiPlannerClient,
    LLMPlannerClient,
    MockLLMPlannerClient,
    RawPlannerOutput,
    RawRule,
)
from app.models import utc_now
from app.repositories import WatchRepository
from app.schemas import (
    Cadence,
    ScheduleInput,
    WatchCreate,
    WatchPlan,
    WatchPlanPreviewResponse,
    WatchPlanSchedule,
)

logger = logging.getLogger(__name__)

SUPPORTED_DOMAINS = {"daraz.pk", "www.daraz.pk"}
DEFAULT_DARAZ_COLLECTOR_ID = "c_msz0zrtw29tjzhzakl"
SUPPORTED_RULE_TYPES = {
    "price_below",
    "price_above",
    "price_drop",
    "back_in_stock",
    "availability_changed",
}


def normalize_numeric_threshold(val: Any) -> float | None:
    """Normalize numeric threshold from string, int, float, or abbreviations like '3k'."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val) if val >= 0 else None

    text = str(val).strip().lower().replace(",", "")
    # Check for '3k' or '2.5k'
    match_k = re.search(r"(\d+(?:\.\d+)?)\s*k\b", text)
    if match_k:
        return float(match_k.group(1)) * 1000.0

    match_num = re.search(r"(\d+(?:\.\d+)?)", text)
    if match_num:
        return float(match_num.group(1))

    return None


def parse_natural_currency(text: str) -> str:
    """Normalize currency expressions to standard ISO codes."""
    s = text.upper()
    if "RS" in s or "PKR" in s or "RUPEE" in s:
        return "PKR"
    if "USD" in s or "$" in s:
        return "USD"
    if "EUR" in s or "€" in s:
        return "EUR"
    return "PKR"


def parse_natural_cadence(text: str) -> tuple[Cadence, int]:
    """Convert natural cadence expression to (Cadence, cadence_minutes)."""
    s = text.lower()
    if "30 minute" in s or "30m" in s or "half hour" in s:
        return "custom", 30
    if "6 hour" in s or "6h" in s:
        return "custom", 360
    if "12 hour" in s or "12h" in s:
        return "custom", 720
    if "daily" in s or "every day" in s or "24 hour" in s:
        return "daily", 1440
    if "weekly" in s or "every week" in s:
        return "weekly", 10080
    if "hourly" in s or "every hour" in s or "1 hour" in s or "60 minute" in s:
        return "hourly", 60

    # Extract any explicit minutes or hours
    match_min = re.search(r"every\s*(\d+)\s*(?:minute|min)s?", s)
    if match_min:
        mins = max(15, min(int(match_min.group(1)), 10080))
        return "custom", mins

    match_hr = re.search(r"every\s*(\d+)\s*(?:hour|hr)s?", s)
    if match_hr:
        mins = max(15, min(int(match_hr.group(1)) * 60, 10080))
        return "custom", mins

    return "hourly", 60


class WatchPlanValidator:
    """Deterministic validator and sanitizer for untrusted LLM planner output."""

    def __init__(self, default_collector_id: str | None = None):
        self.default_collector_id = default_collector_id or DEFAULT_DARAZ_COLLECTOR_ID

    def validate_domain(self, url: str | None) -> tuple[bool, str | None, str | None]:
        """Validate syntax and domain support for URL."""
        if not url or not url.strip():
            return False, "missing_url", "No URL provided."

        try:
            parsed = urlparse(url.strip())
            if not parsed.scheme or not parsed.netloc:
                return False, "invalid_url", f"URL '{url}' is malformed."
            netloc = parsed.netloc.lower()
            if ":" in netloc:
                netloc = netloc.split(":")[0]

            is_supported = netloc in SUPPORTED_DOMAINS or netloc.endswith(".daraz.pk")
            if not is_supported:
                return (
                    False,
                    "unsupported_domain",
                    f"Domain '{netloc}' is not supported. Web Radar currently supports daraz.pk product monitoring.",
                )
            return True, None, None
        except Exception as exc:
            return False, "invalid_url", f"Failed to parse URL '{url}': {exc}"

    def validate_and_build_plan(
        self,
        raw_output: RawPlannerOutput,
        *,
        requested_url: str | None = None,
        default_timezone: str = "Asia/Karachi",
    ) -> WatchPlanPreviewResponse:
        """Validate raw model output and build a normalized, safe WatchPlan."""
        # 1. URL Resolution & Domain Validation
        target_url = requested_url or raw_output.url
        is_valid_domain, domain_err_code, domain_err_msg = self.validate_domain(target_url)

        if not target_url or domain_err_code == "missing_url":
            return WatchPlanPreviewResponse(
                status="needs_clarification",
                missing=["url"],
                clarification_prompt="Please provide a valid Daraz product URL to monitor.",
                message="Target URL is required to create a Watch.",
            )

        if domain_err_code == "unsupported_domain":
            return WatchPlanPreviewResponse(
                status="unsupported",
                missing=[],
                message=domain_err_msg,
            )

        if not is_valid_domain:
            return WatchPlanPreviewResponse(
                status="unsupported",
                missing=["url"],
                message=domain_err_msg,
            )

        # 2. Check LLM Clarification status
        if raw_output.status == "needs_clarification" and raw_output.missing_fields:
            return WatchPlanPreviewResponse(
                status="needs_clarification",
                missing=raw_output.missing_fields,
                clarification_prompt=raw_output.clarification_prompt or "Additional details required.",
                message="The instruction is ambiguous or missing required threshold parameters.",
            )

        # 3. Schedule Normalization & Timezone Validation
        sched = raw_output.schedule
        tz_name = sched.timezone or default_timezone
        try:
            ZoneInfo(tz_name)
        except Exception:
            tz_name = default_timezone

        cadence_minutes = max(15, min(int(sched.cadence_minutes or 60), 10080))
        cadence: Cadence = "custom"
        if cadence_minutes == 60:
            cadence = "hourly"
        elif cadence_minutes == 1440:
            cadence = "daily"
        elif cadence_minutes == 10080:
            cadence = "weekly"

        schedule_plan = WatchPlanSchedule(
            cadence=cadence,
            cadence_minutes=cadence_minutes,
            timezone=tz_name,
        )

        # 4. Rules Normalization & Deterministic Validation
        normalized_rules: list[dict[str, Any]] = []
        missing_rule_fields: list[str] = []

        for rule in raw_output.rules:
            rule_type = str(rule.type).lower().strip()
            if rule_type not in SUPPORTED_RULE_TYPES:
                continue

            if rule_type in {"price_below", "price_above"}:
                numeric_val = normalize_numeric_threshold(rule.value)
                if numeric_val is None or numeric_val <= 0:
                    missing_rule_fields.append("price_threshold")
                    continue
                normalized_rules.append(
                    {
                        "type": rule_type,
                        "field": "price",
                        "value": numeric_val,
                        "currency": "PKR",
                    }
                )
            elif rule_type == "price_drop":
                normalized_rules.append(
                    {
                        "type": "price_drop",
                        "field": "price",
                        "currency": "PKR",
                    }
                )
            elif rule_type in {"back_in_stock", "availability_changed"}:
                normalized_rules.append(
                    {
                        "type": rule_type,
                        "field": "availability",
                    }
                )

        if missing_rule_fields:
            return WatchPlanPreviewResponse(
                status="needs_clarification",
                missing=missing_rule_fields,
                clarification_prompt="Please specify a target price threshold (e.g. below Rs 2,500).",
                message="Target price threshold is required for threshold alert rules.",
            )

        if not normalized_rules:
            # Default to price drop if no rules parsed
            normalized_rules.append({"type": "price_drop", "field": "price", "currency": "PKR"})

        # 5. Security & Collector Binding (NEVER trust model-supplied collector ID)
        bound_collector_id = self.default_collector_id

        monitoring_spec: dict[str, Any] = {
            "vertical": "product",
            "currency": "PKR",
            "collector_id": bound_collector_id,
            "rules": normalized_rules,
        }

        # First numeric threshold if available for top-level spec compatibility
        threshold_rule = next((r for r in normalized_rules if "value" in r), None)
        if threshold_rule:
            monitoring_spec["threshold"] = threshold_rule["value"]
            monitoring_spec["field"] = "price"

        title = raw_output.title or "Daraz Monitored Product"
        intent = raw_output.intent or "Monitor product price and stock on Daraz"

        plan = WatchPlan(
            url=target_url,
            title=title,
            vertical="product",
            intent=intent,
            schedule=schedule_plan,
            monitoring_spec=monitoring_spec,
            collector_id=bound_collector_id,
            confidence=1.0,
            assumptions=raw_output.assumptions or ["Daraz PK product price monitoring"],
        )

        return WatchPlanPreviewResponse(
            status="ready",
            plan=plan,
            missing=[],
            message="Plan generated and validated successfully.",
        )


class NaturalLanguageWatchPlanner:
    """Service that orchestrates natural-language interpretation into structured WatchPlans."""

    def __init__(
        self,
        *,
        llm_client: LLMPlannerClient | None = None,
        validator: WatchPlanValidator | None = None,
        default_timezone: str | None = None,
    ):
        settings = get_settings()
        if llm_client is not None:
            self.llm_client = llm_client
        elif settings.gemini_api_key:
            self.llm_client = GeminiPlannerClient(
                api_key=settings.gemini_api_key,
                model_name=settings.gemini_model_name,
                base_url=settings.gemini_base_url,
            )
        else:
            self.llm_client = MockLLMPlannerClient()

        collector_id = settings.bright_data_collector_id or DEFAULT_DARAZ_COLLECTOR_ID
        self.validator = validator or WatchPlanValidator(default_collector_id=collector_id)
        self.default_timezone = default_timezone or settings.default_timezone

    def preview_plan(
        self,
        *,
        message: str,
        url: str | None = None,
        timezone: str | None = None,
    ) -> WatchPlanPreviewResponse:
        """Interpret natural language request and return a previewable, validated WatchPlan."""
        tz_name = timezone or self.default_timezone
        raw_output = self.llm_client.generate_plan(
            user_message=message,
            url=url,
            default_timezone=tz_name,
        )
        return self.validator.validate_and_build_plan(
            raw_output,
            requested_url=url,
            default_timezone=tz_name,
        )

    def create_watch_from_plan(
        self,
        *,
        db: Session,
        user_id: str,
        plan: WatchPlan,
    ) -> Any:
        """Create a persistent Watch in the database from a pre-validated WatchPlan."""
        repo = WatchRepository(db)
        user = repo.get_user(user_id)
        if user is None:
            raise ValueError(f"User with ID '{user_id}' does not exist.")

        # Calculate initial next_due_at in UTC
        tz = ZoneInfo(plan.schedule.timezone)
        now_tz = datetime.now(tz)
        # First scheduled check
        next_due = now_tz

        watch_create = WatchCreate(
            user_id=user.id,
            url=plan.url,
            title=plan.title,
            instruction=plan.intent,
            monitoring_spec=plan.monitoring_spec,
            schedule=ScheduleInput(
                cadence=plan.schedule.cadence,
                timezone=plan.schedule.timezone,
                next_due_at=next_due,
            ),
            status="active",
        )
        return repo.create(watch_create)
