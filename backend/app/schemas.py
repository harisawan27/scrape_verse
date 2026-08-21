from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field, field_validator


WatchStatus = Literal["active", "paused", "archived"]
HealthStatus = Literal["healthy", "running", "attention", "repairing", "failed", "paused"]
Cadence = Literal["hourly", "daily", "weekly", "custom"]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    auth_id: str | None = None


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    auth_id: str | None = None
    created_at: datetime




class ScheduleInput(BaseModel):
    cadence: Cadence
    timezone: str = "UTC"
    next_due_at: datetime

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("timezone must be an IANA timezone, such as Asia/Karachi") from exc
        return value

    @field_validator("next_due_at")
    @classmethod
    def aware_due_time(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("next_due_at must include a timezone offset")
        return value


class ScheduleUpdateInput(BaseModel):
    cadence: Cadence | None = None
    timezone: str | None = None
    next_due_at: datetime | None = None
    enabled: bool | None = None

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        try:
            ZoneInfo(value)
        except Exception as exc:
            raise ValueError("timezone must be an IANA timezone, such as Asia/Karachi") from exc
        return value


class WatchCreate(BaseModel):
    user_id: str
    url: AnyHttpUrl
    title: str = Field(min_length=1, max_length=255)
    instruction: str = Field(min_length=1)
    monitoring_spec: dict[str, Any]
    schedule: ScheduleInput
    status: WatchStatus = "active"


class WatchUpdate(BaseModel):
    url: AnyHttpUrl | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instruction: str | None = Field(default=None, min_length=1)
    monitoring_spec: dict[str, Any] | None = None
    schedule: ScheduleUpdateInput | ScheduleInput | None = None
    status: WatchStatus | None = None



class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    cadence: Cadence
    timezone: str
    next_due_at: datetime
    enabled: bool


class WatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    url: str
    title: str
    instruction: str
    monitoring_spec: dict[str, Any]
    status: WatchStatus
    created_at: datetime
    updated_at: datetime
    schedule: ScheduleRead | None = None



class SnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    run_id: str
    watch_id: str
    payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict, validation_alias="metadata_")
    captured_at: datetime
    extracted_at: datetime
    created_at: datetime


class ChangeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    watch_id: str
    run_id: str
    change_type: str
    details: dict[str, Any]
    created_at: datetime


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    watch_id: str
    run_id: str | None = None
    change_id: str | None = None
    event_type: str
    summary: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    status: str
    condition_snapshot: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None
    created_at: datetime


class ScraperRepairRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    watch_id: str
    run_id: str
    collector_id: str
    refactor_job_id: str | None = None
    repair_prompt: str
    missing_fields: list[str] = Field(default_factory=list)
    status: str
    failure_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class WatchRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    watch_id: str
    scheduled_for: datetime
    status: str
    bright_data_collection_id: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error_code: str | None = None
    error_detail: str | None = None
    snapshot: SnapshotRead | None = None
    changes: list[ChangeRead] = []
    alerts: list[AlertRead] = []
    repair: ScraperRepairRead | None = None


# --- Natural-Language Watch Planner Schemas ---

class WatchPlanRule(BaseModel):
    type: Literal["price_below", "price_above", "price_drop", "back_in_stock", "availability_changed"]
    field: str = "price"
    value: float | None = None
    currency: str = "PKR"


class WatchPlanSchedule(BaseModel):
    cadence: Cadence = "hourly"
    cadence_minutes: int = 60
    timezone: str = "Asia/Karachi"


class WatchPlan(BaseModel):
    url: str
    title: str
    vertical: str = "product"
    intent: str
    schedule: WatchPlanSchedule
    monitoring_spec: dict[str, Any]
    collector_id: str
    confidence: float = 1.0
    assumptions: list[str] = Field(default_factory=list)


class WatchPlanPreviewRequest(BaseModel):
    message: str = Field(min_length=1)
    url: str | None = None
    timezone: str | None = None


class WatchPlanPreviewResponse(BaseModel):
    status: Literal["ready", "needs_clarification", "unsupported"]
    plan: WatchPlan | None = None
    missing: list[str] = Field(default_factory=list)
    clarification_prompt: str | None = None
    message: str | None = None


class WatchCreateFromPlanRequest(BaseModel):
    user_id: str
    plan: WatchPlan


# --- Frontend Control Surface & Read Models ---

class ProductCurrentValue(BaseModel):
    price: float | None = None
    currency: str | None = None
    availability: str | None = None
    title: str | None = None
    seller: str | None = None
    rating: float | None = None
    reviews_count: int | None = None
    extracted_at: datetime | None = None


class WatchSummaryRead(BaseModel):
    id: str
    user_id: str
    url: str
    domain: str
    title: str
    instruction: str
    status: WatchStatus
    health_status: HealthStatus
    cadence: Cadence
    cadence_minutes: int
    timezone: str
    next_due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    latest_run_at: datetime | None = None
    latest_successful_run_at: datetime | None = None
    latest_value: ProductCurrentValue | None = None
    latest_event: AlertRead | None = None
    active_repair_id: str | None = None


class WatchOverviewStats(BaseModel):
    total_runs: int = 0
    successful_runs: int = 0
    failed_runs: int = 0
    total_events: int = 0


class WatchOverviewRead(BaseModel):
    watch: WatchRead
    health_status: HealthStatus
    latest_snapshot: SnapshotRead | None = None
    latest_run: WatchRunRead | None = None
    latest_event: AlertRead | None = None
    active_repair: ScraperRepairRead | None = None
    latest_value: ProductCurrentValue | None = None
    stats: WatchOverviewStats = Field(default_factory=WatchOverviewStats)


class ActivityEventRead(BaseModel):
    id: str
    watch_id: str
    watch_title: str
    watch_url: str
    event_type: str
    summary: str | None = None
    created_at: datetime
    details: dict[str, Any] = Field(default_factory=dict)





