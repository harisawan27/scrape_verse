import json
import logging
import re
from typing import Any

from app.config import Settings, get_settings
from app.schemas import DiscoveredSource
from app.integrations.ai.types import (
    AIProviderError,
    ProviderRateLimitedError,
    ProviderQuotaExhaustedError,
    ProviderUnavailableError,
    ProviderMetadata,
    SearchCandidate,
)
from app.integrations.ai.groq_client import GroqAIClient
from app.integrations.ai.openrouter_client import OpenRouterSearchClient
from app.integrations.ai.official_ranker import OfficialSourceRanker

logger = logging.getLogger(__name__)


class AIRouterResult:
    """Standardized response from AIRouter."""

    def __init__(
        self,
        mode: str,
        content: str,
        sources: list[DiscoveredSource] | None = None,
        watch_title: str | None = None,
        watch_url: str | None = None,
        watch_intent: str | None = None,
        cadence_minutes: int = 1440,
        cadence_name: str = "daily",
        rules: list[dict[str, Any]] | None = None,
        targets: list[dict[str, Any]] | None = None,
        clarification_options: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.mode = mode
        self.content = content
        self.sources = sources or []
        self.watch_title = watch_title
        self.watch_url = watch_url
        self.watch_intent = watch_intent
        self.cadence_minutes = cadence_minutes
        self.cadence_name = cadence_name
        self.rules = rules or []
        self.targets = targets or []
        self.clarification_options = clarification_options or []
        self.metadata = metadata or {}


class AIRouter:
    """
    Central AI Provider Router for Web Radar.
    Routes normal LLM reasoning, intent classification, and Watch Chat to GROQ.
    Routes fresh public-web discovery ONLY to OPENROUTER + GEMINI.
    Enforces official first-party source ranking and deterministic scan isolation.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        groq_client: GroqAIClient | None = None,
        openrouter_client: OpenRouterSearchClient | None = None,
    ):
        self.settings = settings or get_settings()
        self.groq = groq_client or GroqAIClient(
            api_key=self.settings.groq_api_key,
            default_model=self.settings.groq_default_model,
            reasoning_model=self.settings.groq_reasoning_model,
            base_url=self.settings.groq_base_url,
        )
        self.openrouter = openrouter_client or OpenRouterSearchClient(
            api_key=self.settings.openrouter_api_key,
            search_model=self.settings.openrouter_search_model,
            base_url=self.settings.openrouter_base_url,
        )

    def route_conversational_turn(
        self,
        *,
        message: str,
        url: str | None = None,
        selected_option: str | None = None,
        history: list[dict[str, str]] | None = None,
    ) -> AIRouterResult:
        """
        Main Conversational Discovery & Planning Pipeline:
        1. Groq classifies intent and determines if web search is needed.
        2. If explicit URL supplied -> skips search to save quota.
        3. If search needed -> OpenRouter+Gemini searches -> OfficialSourceRanker ranks first-party URLs.
        4. Groq synthesizes structured plan.
        """
        raw_msg = message.strip()
        if selected_option:
            raw_msg = f"User selected option: '{selected_option}'. Context query: {message}"

        # 1. Intent & Needs-Search Classification via Groq
        classification = self.groq.classify_intent(raw_msg, url=url)

        # Handle Ambiguity / Clarification early without burning search quota
        if classification.mode == "CLARIFICATION" and not selected_option:
            return AIRouterResult(
                mode="CLARIFICATION",
                content=f"I found multiple well-known institutions matching your request. Which one would you like me to monitor?",
                clarification_options=classification.clarification_options,
                metadata={"provider": "groq", "model": self.groq.default_model, "used_web_search": False},
            )

        # 2. Check if fresh public web search is required
        needs_search = classification.needs_web_search and (classification.explicit_url is None)

        discovered_candidates: list[SearchCandidate] = []
        search_summary: str | None = None
        search_meta = ProviderMetadata(provider="groq", model=self.groq.default_model, used_web_search=False)

        if needs_search and self.openrouter.is_configured():
            try:
                search_result = self.openrouter.discover_web(raw_msg)
                search_summary = search_result.raw_answer
                # 3. Apply Official-Source Priority Ranker
                discovered_candidates = OfficialSourceRanker.rank_candidates(raw_msg, search_result.candidates)
                if search_result.metadata:
                    search_meta = search_result.metadata
            except (ProviderRateLimitedError, ProviderQuotaExhaustedError, ProviderUnavailableError) as exc:
                logger.warning("Web search provider unavailable (%s): %s", exc.error_category, exc)
                return AIRouterResult(
                    mode="ASK",
                    content="Web discovery is temporarily unavailable due to search provider quota limits. Please provide a direct URL to monitor.",
                    metadata={"provider": "openrouter", "error": exc.error_category, "used_web_search": True},
                )
            except Exception as exc:
                logger.exception("Unexpected search discovery error: %s", exc)

        elif classification.explicit_url:
            # Explicit URL supplied -> zero search requests needed
            discovered_candidates = [
                SearchCandidate(
                    url=classification.explicit_url,
                    title=raw_msg[:50],
                    is_official=True,
                    priority_score=100,
                )
            ]

        # 4. Groq converts discovery results into structured monitoring plan
        plan, groq_meta = self.groq.synthesize_plan(
            user_query=raw_msg,
            mode=classification.mode,
            discovered_candidates=discovered_candidates,
            search_summary=search_summary,
        )

        # Build schema DiscoveredSource list preserving grounding
        sources = [
            DiscoveredSource(
                url=c.url,
                title=c.title,
                target_type=c.target_type,
                confidence=float(c.priority_score) / 100.0,
                official=c.is_official,
            )
            for c in discovered_candidates[:5]
        ]

        primary_url = plan.get("primary_url")
        if not primary_url and discovered_candidates:
            primary_url = discovered_candidates[0].url

        # Structured rules and targets
        rules = plan.get("rules", [])
        if not rules and classification.mode in ("WATCH", "ASK_AND_WATCH"):
            rules = [{"type": "availability_changed", "field": "status", "value": "updated"}]

        targets = [
            {"url": s.url, "target_type": s.target_type, "source_confidence": s.confidence}
            for s in sources
        ]

        metadata = {
            "provider": search_meta.provider if search_meta.used_web_search else groq_meta.provider,
            "model": search_meta.model if search_meta.used_web_search else groq_meta.model,
            "used_web_search": search_meta.used_web_search,
            "groq_model": groq_meta.model,
        }

        return AIRouterResult(
            mode=classification.mode,
            content=plan.get("content") or search_summary or f"Evaluated request for {raw_msg}",
            sources=sources,
            watch_title=plan.get("title") or (sources[0].title if sources else raw_msg[:50]),
            watch_url=primary_url if classification.mode != "ASK" else None,
            watch_intent=raw_msg,
            cadence_minutes=plan.get("cadence_minutes", 1440),
            cadence_name=plan.get("cadence_name", "daily"),
            rules=rules,
            targets=targets,
            metadata=metadata,
        )

    def explain_watch_status(
        self,
        *,
        overview_data: dict[str, Any],
        user_question: str,
    ) -> tuple[str, ProviderMetadata]:
        """Watch Chat: Explains why a watch has/has not alerted using Groq (0 search calls)."""
        prompt = (
            f"You are Web Radar's contextual Watch Assistant.\n"
            f"User Question: '{user_question}'\n\n"
            f"Live Monitored Database State:\n"
            f"{json.dumps(overview_data, indent=2, default=str)}\n\n"
            f"Instructions:\n"
            f"1. Explain clearly to the user why an alert has or has not fired based on the current selling price vs active rule threshold.\n"
            f"2. Cite the exact current selling price and active rule threshold.\n"
            f"3. Note the scraper health and execution run count."
        )
        messages = [
            {"role": "system", "content": "You are a helpful monitoring assistant for Web Radar."},
            {"role": "user", "content": prompt},
        ]
        content, meta = self.groq._call_groq(messages=messages, model=self.groq.default_model, temperature=0.1)
        return content, meta
