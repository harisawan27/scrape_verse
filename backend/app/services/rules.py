"""Deterministic Watch rules evaluation and semantic event generation.

Evaluates structured product/price rules without LLM tokens.
"""

from dataclasses import dataclass
import logging
from typing import Any

from app.models import Watch

logger = logging.getLogger(__name__)


@dataclass
class SemanticEvent:
    event_type: str
    summary: str
    details: dict[str, Any]
    condition_snapshot: dict[str, Any]
    idempotency_key: str


def normalize_numeric_price(val: Any) -> float | None:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, str):
        cleaned = val.strip().replace(",", "")
        # Remove currency prefix if present
        for prefix in ("PKR", "USD", "EUR", "GBP", "Rs.", "Rs", "$"):
            if cleaned.upper().startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def normalize_availability_status(val: Any) -> str:
    if val is None:
        return "unknown"
    if isinstance(val, bool):
        return "in_stock" if val else "out_of_stock"
    if isinstance(val, str):
        v = val.strip().lower().replace("-", "_").replace(" ", "_")
        if v in {"in_stock", "instock", "available", "true"}:
            return "in_stock"
        if v in {"out_of_stock", "outofstock", "sold_out", "soldout", "unavailable", "false"}:
            return "out_of_stock"
    return "unknown"


def normalize_currency_code(val: Any) -> str:
    if val is None or not isinstance(val, str):
        return "PKR"
    return val.strip().upper()


class RuleEvaluator:
    """Evaluates rules deterministically across current and previous snapshots."""

    @classmethod
    def evaluate(
        cls,
        watch: Watch,
        current_payload: dict[str, Any],
        previous_payload: dict[str, Any] | None = None,
        run_id: str | None = None,
    ) -> list[SemanticEvent]:
        if not current_payload:
            return []

        events: list[SemanticEvent] = []
        rules = cls._extract_rules(watch)

        curr_price = normalize_numeric_price(current_payload.get("price"))
        curr_currency = normalize_currency_code(current_payload.get("currency", "PKR"))
        curr_avail = normalize_availability_status(current_payload.get("availability"))

        prev_price = normalize_numeric_price(previous_payload.get("price")) if previous_payload else None
        prev_currency = normalize_currency_code(previous_payload.get("currency", "PKR")) if previous_payload else None
        prev_avail = normalize_availability_status(previous_payload.get("availability")) if previous_payload else None

        # 1. Evaluate configured explicit rules
        for rule in rules:
            rule_type = rule.get("type")
            rule_field = rule.get("field", "price")

            if rule_type == "price_below":
                threshold = normalize_numeric_price(rule.get("value") or rule.get("threshold"))
                rule_curr = normalize_currency_code(rule.get("currency", curr_currency))
                if threshold is None or curr_price is None:
                    continue

                # Incompatible currencies check
                if curr_currency != rule_curr or (prev_currency and prev_currency != rule_curr):
                    logger.warning("Currency mismatch for rule %s: %s vs %s", rule, curr_currency, rule_curr)
                    continue

                # Crossing semantics: previous price was strictly above threshold, current price is at or below threshold
                if prev_price is not None and prev_price > threshold and curr_price <= threshold:
                    events.append(
                        SemanticEvent(
                            event_type="price_threshold_crossed",
                            summary=(
                                f"Price dropped from {curr_currency} {prev_price:,.2f} to "
                                f"{curr_currency} {curr_price:,.2f} and crossed below threshold {curr_currency} {threshold:,.2f}"
                            ),
                            details={
                                "field": "price",
                                "previous_value": prev_price,
                                "current_value": curr_price,
                                "currency": curr_currency,
                                "rule_type": "price_below",
                                "rule_value": threshold,
                            },
                            condition_snapshot=rule,
                            idempotency_key=f"{run_id or 'run'}:price_threshold_crossed:price_below:{threshold}",
                        )
                    )

            elif rule_type == "price_above":
                threshold = normalize_numeric_price(rule.get("value") or rule.get("threshold"))
                rule_curr = normalize_currency_code(rule.get("currency", curr_currency))
                if threshold is None or curr_price is None:
                    continue

                if curr_currency != rule_curr or (prev_currency and prev_currency != rule_curr):
                    continue

                # Crossing semantics: previous price was strictly below threshold, current price is at or above threshold
                if prev_price is not None and prev_price < threshold and curr_price >= threshold:
                    events.append(
                        SemanticEvent(
                            event_type="price_threshold_crossed",
                            summary=(
                                f"Price increased from {curr_currency} {prev_price:,.2f} to "
                                f"{curr_currency} {curr_price:,.2f} and crossed above threshold {curr_currency} {threshold:,.2f}"
                            ),
                            details={
                                "field": "price",
                                "previous_value": prev_price,
                                "current_value": curr_price,
                                "currency": curr_currency,
                                "rule_type": "price_above",
                                "rule_value": threshold,
                            },
                            condition_snapshot=rule,
                            idempotency_key=f"{run_id or 'run'}:price_threshold_crossed:price_above:{threshold}",
                        )
                    )

            elif rule_type == "back_in_stock":
                if prev_avail is not None and prev_avail in {"out_of_stock", "unknown"} and curr_avail == "in_stock":
                    events.append(
                        SemanticEvent(
                            event_type="back_in_stock",
                            summary="Product is back in stock!",
                            details={
                                "field": "availability",
                                "previous_value": prev_avail,
                                "current_value": curr_avail,
                                "rule_type": "back_in_stock",
                            },
                            condition_snapshot=rule,
                            idempotency_key=f"{run_id or 'run'}:back_in_stock:availability",
                        )
                    )

            elif rule_type == "availability_changed":
                if prev_avail is not None and prev_avail != curr_avail and curr_avail != "unknown":
                    events.append(
                        SemanticEvent(
                            event_type="availability_changed",
                            summary=f"Product availability changed from '{prev_avail}' to '{curr_avail}'",
                            details={
                                "field": "availability",
                                "previous_value": prev_avail,
                                "current_value": curr_avail,
                                "rule_type": "availability_changed",
                            },
                            condition_snapshot=rule,
                            idempotency_key=f"{run_id or 'run'}:availability_changed:availability",
                        )
                    )

        # 2. General baseline movement events (when previous snapshot exists and currency matches)
        if prev_price is not None and curr_price is not None and prev_currency == curr_currency:
            if curr_price < prev_price:
                diff = prev_price - curr_price
                pct = round((diff / prev_price) * 100, 2)
                events.append(
                    SemanticEvent(
                        event_type="price_decreased",
                        summary=f"Price decreased by {curr_currency} {diff:,.2f} ({pct}%) from {curr_currency} {prev_price:,.2f} to {curr_currency} {curr_price:,.2f}",
                        details={
                            "field": "price",
                            "previous_value": prev_price,
                            "current_value": curr_price,
                            "currency": curr_currency,
                            "drop_amount": diff,
                            "percentage_drop": pct,
                        },
                        condition_snapshot={"type": "price_drop", "field": "price"},
                        idempotency_key=f"{run_id or 'run'}:price_decreased:price",
                    )
                )
            elif curr_price > prev_price:
                diff = curr_price - prev_price
                pct = round((diff / prev_price) * 100, 2)
                events.append(
                    SemanticEvent(
                        event_type="price_increased",
                        summary=f"Price increased by {curr_currency} {diff:,.2f} (+{pct}%) from {curr_currency} {prev_price:,.2f} to {curr_currency} {curr_price:,.2f}",
                        details={
                            "field": "price",
                            "previous_value": prev_price,
                            "current_value": curr_price,
                            "currency": curr_currency,
                            "increase_amount": diff,
                            "percentage_increase": pct,
                        },
                        condition_snapshot={"type": "price_increase", "field": "price"},
                        idempotency_key=f"{run_id or 'run'}:price_increased:price",
                    )
                )

        # 3. Availability transition event if not already emitted by explicit rule
        if prev_avail is not None and prev_avail != curr_avail and curr_avail != "unknown":
            has_avail_event = any(e.event_type in {"availability_changed", "back_in_stock"} for e in events)
            if not has_avail_event:
                if prev_avail in {"out_of_stock", "unknown"} and curr_avail == "in_stock":
                    events.append(
                        SemanticEvent(
                            event_type="back_in_stock",
                            summary="Product is back in stock!",
                            details={
                                "field": "availability",
                                "previous_value": prev_avail,
                                "current_value": curr_avail,
                                "rule_type": "back_in_stock",
                            },
                            condition_snapshot={"type": "back_in_stock", "field": "availability"},
                            idempotency_key=f"{run_id or 'run'}:back_in_stock:availability",
                        )
                    )
                else:
                    events.append(
                        SemanticEvent(
                            event_type="availability_changed",
                            summary=f"Product availability changed from '{prev_avail}' to '{curr_avail}'",
                            details={
                                "field": "availability",
                                "previous_value": prev_avail,
                                "current_value": curr_avail,
                                "rule_type": "availability_changed",
                            },
                            condition_snapshot={"type": "availability_changed", "field": "availability"},
                            idempotency_key=f"{run_id or 'run'}:availability_changed:availability",
                        )
                    )

        return events

    @classmethod
    def _extract_rules(cls, watch: Watch) -> list[dict[str, Any]]:
        spec = watch.monitoring_spec if isinstance(watch.monitoring_spec, dict) else {}
        if "rules" in spec and isinstance(spec["rules"], list):
            return spec["rules"]

        # Synthesize rule from legacy/simple monitoring_spec
        rules: list[dict[str, Any]] = []
        threshold = spec.get("threshold") or spec.get("value")
        if threshold is not None:
            rules.append(
                {
                    "type": "price_below",
                    "field": "price",
                    "value": threshold,
                    "currency": spec.get("currency", "PKR"),
                }
            )
        return rules
