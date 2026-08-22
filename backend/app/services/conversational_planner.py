import logging
from typing import Any

from app.config import get_settings
from app.schemas import DiscoveredSource
from app.integrations.ai.router import AIRouter, AIRouterResult

logger = logging.getLogger(__name__)


class ConversationalIntent:
    ASK = "ASK"
    WATCH = "WATCH"
    ASK_AND_WATCH = "ASK_AND_WATCH"
    CLARIFICATION = "CLARIFICATION"


# Re-export ConversationalPlanResult pointing to AIRouterResult for backwards compatibility
ConversationalPlanResult = AIRouterResult


class ConversationalDiscoveryEngine:
    """
    Intelligent Conversational Engine for Web Radar.
    Delegates to central AIRouter:
    - Groq for fast intent classification, reasoning, and plan synthesis.
    - OpenRouter + Gemini for real-time web discovery with Official-Source Priority.
    """

    def __init__(
        self,
        router: AIRouter | None = None,
        gemini_api_key: str | None = None,
        model_name: str | None = None,
        base_url: str | None = None,
    ):
        self.router = router or AIRouter(get_settings())

    def plan_conversation(
        self,
        *,
        message: str,
        url: str | None = None,
        selected_option: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AIRouterResult:
        """Process user message through central AIRouter pipeline."""
        return self.router.route_conversational_turn(
            message=message,
            url=url,
            selected_option=selected_option,
            history=history,
        )
