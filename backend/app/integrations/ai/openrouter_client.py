import json
import logging
import re
from urllib.parse import urlparse
from typing import Any
import httpx

from app.integrations.ai.types import (
    AIProviderError,
    ProviderRateLimitedError,
    ProviderQuotaExhaustedError,
    ProviderAuthFailedError,
    ProviderUnavailableError,
    ProviderMetadata,
    SearchCandidate,
    DiscoveredWebResult,
)

logger = logging.getLogger(__name__)


class OpenRouterSearchClient:
    """
    Search-only AI client for Web Radar.
    Routes queries requiring fresh public-web discovery to OpenRouter + Gemini Search.
    NEVER used for non-search tasks (e.g. Watch Chat, summaries, rule updates).
    """

    def __init__(
        self,
        api_key: str | None,
        search_model: str = "google/gemini-2.5-flash",
        base_url: str = "https://openrouter.ai/api/v1",
        timeout_seconds: float = 25.0,
    ):
        self.api_key = api_key
        self.search_model = search_model
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds

    def is_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    def discover_web(self, query: str) -> DiscoveredWebResult:
        """Perform real web search discovery and extract candidate URLs with evidence."""
        if not self.is_configured():
            raise ProviderUnavailableError("OpenRouter API key is not configured for web discovery.", provider="openrouter")

        prompt = (
            f"You are Web Radar's Search Discovery Engine.\n"
            f"User Query: {query}\n\n"
            f"Instructions:\n"
            f"1. Search the live web to find accurate, real-world information and official website URLs.\n"
            f"2. Cite official website URLs explicitly in markdown link format: [Website Title](https://example.com).\n"
            f"3. Prioritize first-party official domains (e.g. official university, company, or store domain) over third-party aggregators."
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://webradar.dev",
            "X-Title": "Web Radar",
        }
        payload: dict[str, Any] = {
            "model": self.search_model,
            "messages": [{"role": "user", "content": prompt}],
            "plugins": [{"id": "web"}],
            "max_tokens": 1000,
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)

            if response.status_code == 429:
                err_text = response.text
                if "quota" in err_text.lower() or "credits" in err_text.lower():
                    raise ProviderQuotaExhaustedError(f"OpenRouter quota exhausted: {err_text}", provider="openrouter")
                raise ProviderRateLimitedError(f"OpenRouter rate limit: {err_text}", provider="openrouter")
            elif response.status_code == 402:
                raise ProviderQuotaExhaustedError(f"OpenRouter insufficient credits: {response.text}", provider="openrouter")
            elif response.status_code in (401, 403):
                raise ProviderAuthFailedError(f"OpenRouter authorization failed: {response.text}", provider="openrouter")
            elif response.status_code != 200:
                raise AIProviderError(f"OpenRouter returned HTTP {response.status_code}: {response.text}", provider="openrouter")

            data = response.json()
            choices = data.get("choices", [])
            if not choices:
                raise AIProviderError("No choices returned from OpenRouter discovery", provider="openrouter")

            raw_text = choices[0].get("message", {}).get("content", "").strip()
            usage = data.get("usage", {})
            metadata = ProviderMetadata(
                provider="openrouter",
                model=self.search_model,
                used_web_search=True,
                tokens_used=usage.get("total_tokens"),
            )

            # Extract URLs from markdown links [Title](URL) and raw text
            candidates: list[SearchCandidate] = []
            seen_urls = set()

            # 1. Parse markdown links
            md_links = re.findall(r"\[([^\]]+)\]\((https?://[^\s)]+)\)", raw_text)
            for title, uri in md_links:
                uri_clean = uri.rstrip(".,;)")
                if uri_clean not in seen_urls:
                    seen_urls.add(uri_clean)
                    candidates.append(
                        SearchCandidate(
                            url=uri_clean,
                            title=title.strip(),
                            target_type="primary",
                        )
                    )

            # 2. Parse raw URLs
            raw_urls = re.findall(r"https?://[^\s)\]\"'>]+", raw_text)
            for uri in raw_urls:
                uri_clean = uri.rstrip(".,;)")
                if uri_clean not in seen_urls:
                    seen_urls.add(uri_clean)
                    parsed = urlparse(uri_clean)
                    domain = parsed.netloc or uri_clean
                    candidates.append(
                        SearchCandidate(
                            url=uri_clean,
                            title=domain,
                            target_type="primary",
                        )
                    )

            return DiscoveredWebResult(
                raw_answer=raw_text,
                candidates=candidates,
                metadata=metadata,
            )

        except httpx.TimeoutException as exc:
            raise ProviderUnavailableError(f"OpenRouter search timed out: {exc}", provider="openrouter") from exc
        except httpx.RequestError as exc:
            raise ProviderUnavailableError(f"OpenRouter search network error: {exc}", provider="openrouter") from exc
