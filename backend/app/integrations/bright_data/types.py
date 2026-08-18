from dataclasses import dataclass, field
from typing import Any


class BrightDataError(Exception):
    """Base exception for Bright Data API interactions."""
    pass


class BrightDataAuthError(BrightDataError):
    """Raised when authentication fails (HTTP 401/403)."""
    pass


class BrightDataNotFoundError(BrightDataError):
    """Raised when the specified collector or snapshot is not found (HTTP 404)."""
    pass


class BrightDataRateLimitError(BrightDataError):
    """Raised when API rate limits are exceeded (HTTP 429)."""
    pass


class BrightDataTimeoutError(BrightDataError):
    """Raised when a collection exceeds maximum polling timeout."""
    pass


@dataclass(frozen=True)
class CollectionTriggerResult:
    """Result of submitting a collection job to Bright Data."""
    collection_id: str
    status: str = "running"
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CollectionProgress:
    """Current processing state of a collection job."""
    collection_id: str
    status: str  # "pending", "running", "ready", "failed"
    progress: float = 0.0
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status.lower() in {"ready", "completed", "succeeded"}

    @property
    def is_failed(self) -> bool:
        return self.status.lower() in {"failed", "error", "canceled"}


@dataclass(frozen=True)
class RefactorTriggerResult:
    """Result of triggering a self-healing refactor on a collector."""
    collector_id: str
    job_id: str | None = None
    status: str = "in_progress"
    raw_response: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RefactorProgress:
    """Status of an in-flight scraper refactor."""
    collector_id: str
    status: str  # "in_progress", "pending_answer", "ready", "applied", "failed"
    progress: float = 0.0
    error: str | None = None
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def is_ready(self) -> bool:
        return self.status.lower() in {"ready", "pending_answer", "done"}

    @property
    def is_failed(self) -> bool:
        return self.status.lower() in {"failed", "error"}

    @property
    def requires_approval(self) -> bool:
        return self.status.lower() in {"pending_answer"}

