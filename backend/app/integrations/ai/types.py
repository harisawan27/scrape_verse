from dataclasses import dataclass, field
from typing import Any


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(self, message: str, provider: str = "unknown", error_category: str = "provider_error"):
        super().__init__(message)
        self.provider = provider
        self.error_category = error_category


class ProviderRateLimitedError(AIProviderError):
    """Raised when an AI provider responds with HTTP 429 or rate limit."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, error_category="provider_rate_limited")


class ProviderQuotaExhaustedError(AIProviderError):
    """Raised when an AI provider account has exhausted credits/quota."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, error_category="provider_quota_exhausted")


class ProviderAuthFailedError(AIProviderError):
    """Raised when an AI provider returns 401 or 403 authorization failure."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, error_category="provider_auth_failed")


class ProviderUnavailableError(AIProviderError):
    """Raised when an AI provider is unreachable or times out."""

    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, provider=provider, error_category="provider_unavailable")


@dataclass
class ProviderMetadata:
    """Internal lightweight observability metadata."""
    provider: str
    model: str
    used_web_search: bool = False
    tokens_used: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "used_web_search": self.used_web_search,
        }


@dataclass
class SearchCandidate:
    """A discovered candidate web destination."""
    url: str
    title: str
    snippet: str | None = None
    target_type: str = "primary"
    is_official: bool = False
    priority_score: int = 50  # higher is better


@dataclass
class DiscoveredWebResult:
    """Result of an external web search discovery operation."""
    raw_answer: str
    candidates: list[SearchCandidate] = field(default_factory=list)
    metadata: ProviderMetadata | None = None


@dataclass
class IntentClassification:
    """Result of intent analysis by Groq."""
    mode: str  # ASK, WATCH, ASK_AND_WATCH, CLARIFICATION
    needs_web_search: bool
    is_ambiguous: bool = False
    clarification_options: list[str] = field(default_factory=list)
    explicit_url: str | None = None
    entity_name: str | None = None
