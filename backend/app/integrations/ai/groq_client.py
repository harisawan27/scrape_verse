import json
import logging
import re
from typing import Any
import httpx

from app.integrations.ai.types import (
    AIProviderError,
    ProviderRateLimitedError,
    ProviderQuotaExhaustedError,
    ProviderAuthFailedError,
    ProviderUnavailableError,
    ProviderMetadata,
    IntentClassification,
    SearchCandidate,
)

logger = logging.getLogger(__name__)


class GroqAIClient:
    """
    Groq AI Client for Web Radar.
    Handles routine LLM tasks: intent classification, reasoning, plan synthesis,
    rule explanations, and natural-language Watch Chat with ultra-low latency.
    """

    def __init__(
        self,
        api_key: str | None,
        default_model: str = "openai/gpt-oss-120b",
        reasoning_model: str = "openai/gpt-oss-120b",
        base_url: str = "https://api.groq.com/openai/v1",
        timeout_seconds: float = 20.0,
    ):
        self.api_key = api_key
        self.default_model = default_model
        self.reasoning_model = reasoning_model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def _call_groq(
        self,
        *,
        messages: list[dict[str, str]],
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
        json_mode: bool = False,
    ) -> tuple[str, ProviderMetadata]:
        """Execute chat completion request against Groq API with robust error handling."""
        if not self.is_configured():
            raise ProviderUnavailableError("Groq API key is not configured.", provider="groq")

        selected_model = model or self.default_model
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: dict[str, Any] = {
            "model": selected_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)

            if response.status_code == 429:
                err_text = response.text
                if "quota" in err_text.lower():
                    raise ProviderQuotaExhaustedError(f"Groq quota exhausted: {err_text}", provider="groq")
                raise ProviderRateLimitedError(f"Groq rate limit exceeded: {err_text}", provider="groq")
            elif response.status_code in (401, 403):
                raise ProviderAuthFailedError(f"Groq authentication failed: {response.text}", provider="groq")
            elif response.status_code != 200:
                raise AIProviderError(f"Groq returned HTTP {response.status_code}: {response.text}", provider="groq")

            data = response.json()
            content = data["choices"][0]["message"]["content"]
            usage = data.get("usage", {})
            metadata = ProviderMetadata(
                provider="groq",
                model=selected_model,
                used_web_search=False,
                tokens_used=usage.get("total_tokens"),
            )
            return content, metadata

        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"Groq request timed out: {exc}", provider="groq") from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(f"Groq network error: {exc}", provider="groq") from exc

    def classify_intent(self, message: str, url: str | None = None) -> IntentClassification:
        """Classify user intent and determine if fresh web search discovery is required."""
        msg = message.strip()
        msg_lower = msg.lower()

        # Check for explicit URL supplied
        explicit_url = url
        if not explicit_url:
            match_url = re.search(r"https?://[^\s)\]\"'>]+", msg)
            if match_url:
                explicit_url = match_url.group(0).rstrip(".,;)")

        # Fast heuristic ambiguity detection for known polysemous acronyms
        if ("bau university" in msg_lower or "bau " in msg_lower or msg_lower == "bau") and not any(k in msg_lower for k in ["bahçeşehir", "bahcesehir", "beirut", "bangladesh"]):
            return IntentClassification(
                mode="CLARIFICATION",
                needs_web_search=False,
                is_ambiguous=True,
                clarification_options=[
                    "Bahçeşehir University (Istanbul, Türkiye)",
                    "Beirut Arab University (Beirut, Lebanon)",
                    "Bangladesh Agricultural University (Mymensingh, Bangladesh)",
                ],
                entity_name="BAU",
                explicit_url=explicit_url,
            )

        # If user explicitly supplied a URL, no search is required
        if explicit_url:
            is_watch = any(k in msg_lower for k in ["watch", "monitor", "alert", "track", "check every", "notify"])
            return IntentClassification(
                mode="WATCH" if is_watch else "ASK",
                needs_web_search=False,
                explicit_url=explicit_url,
            )

        # Call Groq for structured classification
        sys_prompt = (
            "You are Web Radar's Intent Classifier.\n"
            "Analyze the user prompt and return a strictly valid JSON object:\n"
            "{\n"
            '  "mode": "ASK" | "WATCH" | "ASK_AND_WATCH" | "CLARIFICATION",\n'
            '  "needs_web_search": boolean,\n'
            '  "entity_name": string or null,\n'
            '  "is_ambiguous": boolean,\n'
            '  "clarification_options": [string]\n'
            "}\n"
            "Rules:\n"
            "- ASK: User wants one-time factual answer or contact info.\n"
            "- WATCH: User wants ongoing monitoring without immediate factual question.\n"
            "- ASK_AND_WATCH: User asks for current status AND wants continuous background monitoring.\n"
            "- needs_web_search: true if entity/URL needs to be discovered on the public web.\n"
            "- is_ambiguous: true if acronym/name has multiple distinct real-world institutions.\n"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": msg},
        ]

        try:
            content, _ = self._call_groq(messages=messages, model=self.default_model, temperature=0.1, json_mode=True)
            parsed = json.loads(content)
            return IntentClassification(
                mode=parsed.get("mode", "ASK"),
                needs_web_search=parsed.get("needs_web_search", True),
                is_ambiguous=parsed.get("is_ambiguous", False),
                clarification_options=parsed.get("clarification_options", []),
                entity_name=parsed.get("entity_name"),
                explicit_url=explicit_url,
            )
        except Exception as exc:
            logger.warning("Groq intent classification fallback: %s", exc)
            # Safe deterministic classification fallback
            is_watch = any(k in msg_lower for k in ["watch", "monitor", "alert", "track", "notify", "tell me when"])
            is_ask = any(k in msg_lower for k in ["find", "what is", "contact", "email", "phone", "check", "info"])
            mode = "ASK_AND_WATCH" if (is_watch and is_ask) else ("WATCH" if is_watch else "ASK")
            return IntentClassification(
                mode=mode,
                needs_web_search=explicit_url is None,
                explicit_url=explicit_url,
            )

    def synthesize_plan(
        self,
        *,
        user_query: str,
        mode: str,
        discovered_candidates: list[SearchCandidate],
        search_summary: str | None = None,
    ) -> tuple[dict[str, Any], ProviderMetadata]:
        """Convert discovered candidates and user query into a structured monitoring plan."""
        sys_prompt = (
            "You are Web Radar's Monitoring Plan Synthesizer.\n"
            "Given the user request and ranked web discovery candidates, generate a structured JSON plan:\n"
            "{\n"
            '  "title": string,\n'
            '  "content": string,\n'
            '  "primary_url": string,\n'
            '  "rules": [{"type": string, "field": string, "value": number or null, "currency": string or null}],\n'
            '  "cadence_minutes": integer,\n'
            '  "cadence_name": string\n'
            "}\n"
            "Instructions:\n"
            "- For ASK mode: provide a clear, factual answer in 'content'. primary_url is the best official source.\n"
            "- For WATCH or ASK_AND_WATCH mode: select the best first-party official URL as primary_url. Create appropriate rules (e.g. price_below if price threshold mentioned, or availability_changed).\n"
        )
        cand_data = [
            {"url": c.url, "title": c.title, "type": c.target_type, "official": c.is_official, "score": c.priority_score}
            for c in discovered_candidates[:5]
        ]
        user_prompt = (
            f"User Query: {user_query}\n"
            f"Mode: {mode}\n"
            f"Discovery Summary: {search_summary or 'None'}\n"
            f"Ranked Candidates:\n{json.dumps(cand_data, indent=2)}"
        )
        messages = [
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ]
        content, meta = self._call_groq(messages=messages, model=self.reasoning_model, temperature=0.2, json_mode=True)
        try:
            plan = json.loads(content)
            return plan, meta
        except Exception as exc:
            logger.warning("Failed to parse Groq synthesized plan: %s", exc)
            fallback_url = discovered_candidates[0].url if discovered_candidates else "https://example.com"
            return {
                "title": user_query[:50],
                "content": search_summary or f"Evaluated request for: {user_query}",
                "primary_url": fallback_url,
                "rules": [{"type": "availability_changed", "field": "status", "value": "updated"}],
                "cadence_minutes": 1440,
                "cadence_name": "daily",
            }, meta
