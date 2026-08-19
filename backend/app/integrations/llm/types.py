from dataclasses import dataclass, field
from typing import Any


@dataclass
class RawRule:
    type: str
    field: str = "price"
    value: float | int | None = None
    currency: str = "PKR"


@dataclass
class RawSchedule:
    cadence_minutes: int = 60
    cadence_name: str | None = None
    timezone: str = "Asia/Karachi"


@dataclass
class RawPlannerOutput:
    url: str | None = None
    title: str | None = None
    vertical: str = "product"
    intent: str = "Monitor product price"
    schedule: RawSchedule = field(default_factory=RawSchedule)
    rules: list[RawRule] = field(default_factory=list)
    status: str = "ready"  # "ready" | "needs_clarification" | "unsupported"
    missing_fields: list[str] = field(default_factory=list)
    clarification_prompt: str | None = None
    assumptions: list[str] = field(default_factory=list)
    suggested_collector_id: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)
