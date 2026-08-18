import logging
from typing import Any, Protocol

import httpx

from app.integrations.bright_data.types import (
    BrightDataAuthError,
    BrightDataError,
    BrightDataNotFoundError,
    BrightDataRateLimitError,
    CollectionProgress,
    CollectionTriggerResult,
)

logger = logging.getLogger(__name__)


class BrightDataAdapter(Protocol):
    """Boundary for Bright Data Scraper Studio / Datasets API."""

    def trigger_collection(
        self,
        *,
        collector_id: str,
        inputs: list[dict[str, Any]],
        webhook_url: str | None = None,
    ) -> CollectionTriggerResult: ...

    def get_collection_status(self, *, collection_id: str) -> CollectionProgress: ...

    def get_collection_result(self, *, collection_id: str) -> list[dict[str, Any]] | None: ...


class MockBrightDataAdapter:
    """Deterministic in-memory adapter for unit testing and local development."""

    def __init__(
        self,
        *,
        preset_collection_id: str | None = None,
        preset_status: str = "ready",
        preset_data: list[dict[str, Any]] | None = None,
        fail_trigger: bool = False,
    ):
        self.preset_collection_id = preset_collection_id
        self.preset_status = preset_status
        self.preset_data = preset_data
        self.fail_trigger = fail_trigger
        self.triggered_calls: list[dict[str, Any]] = []

    def trigger_collection(
        self,
        *,
        collector_id: str,
        inputs: list[dict[str, Any]],
        webhook_url: str | None = None,
    ) -> CollectionTriggerResult:
        import uuid

        if self.fail_trigger:
            raise BrightDataError("Mocked trigger failure")
        self.triggered_calls.append({
            "collector_id": collector_id,
            "inputs": inputs,
            "webhook_url": webhook_url,
        })
        cid = self.preset_collection_id or f"j_mock_{uuid.uuid4().hex[:12]}"
        return CollectionTriggerResult(
            collection_id=cid,
            status="running",
            raw_response={"snapshot_id": cid, "status": "running"},
        )


    def get_collection_status(self, *, collection_id: str) -> CollectionProgress:
        return CollectionProgress(
            collection_id=collection_id,
            status=self.preset_status,
            progress=1.0 if self.preset_status == "ready" else 0.5,
            raw_response={"status": self.preset_status},
        )

    def get_collection_result(self, *, collection_id: str) -> list[dict[str, Any]] | None:
        if self.preset_status != "ready":
            return None
        if self.preset_data is not None:
            return self.preset_data
        return [
            {
                "url": "https://example.com/product",
                "title": "Mock Product",
                "price": 2499,
                "currency": "PKR",
                "availability": "in_stock",
            }
        ]


class HttpBrightDataAdapter:
    """Production HTTP client for Bright Data Scraper Studio & Datasets v3 API."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.brightdata.com",
        timeout_seconds: float = 30.0,
        http_client: httpx.Client | None = None,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._client = http_client or httpx.Client(timeout=timeout_seconds)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _handle_error_response(self, response: httpx.Response, action: str) -> None:
        if response.status_code == 401 or response.status_code == 403:
            raise BrightDataAuthError(f"Bright Data authentication failed during {action}: {response.status_code}")
        if response.status_code == 404:
            raise BrightDataNotFoundError(f"Bright Data resource not found during {action}: {response.status_code}")
        if response.status_code == 429:
            raise BrightDataRateLimitError(f"Bright Data rate limit exceeded during {action}: {response.status_code}")
        if response.is_error:
            raise BrightDataError(
                f"Bright Data API error during {action} ({response.status_code}): {response.text[:300]}"
            )

    def trigger_collection(
        self,
        *,
        collector_id: str,
        inputs: list[dict[str, Any]],
        webhook_url: str | None = None,
    ) -> CollectionTriggerResult:
        """Trigger an asynchronous collection job for Scraper Studio (c_...) or Datasets v3 (gd_...)."""
        is_dca = collector_id.startswith("c_")
        if is_dca:
            url = f"{self.base_url}/dca/trigger"
            params: dict[str, str] = {"collector": collector_id, "queue_next": "1"}
            if webhook_url:
                params["endpoint"] = webhook_url
        else:
            url = f"{self.base_url}/datasets/v3/trigger"
            params = {"dataset_id": collector_id, "include_errors": "true"}
            if webhook_url:
                params["endpoint"] = webhook_url
                params["uncompressed_webhook"] = "true"

        try:
            response = self._client.post(
                url,
                params=params,
                json=inputs,
                headers=self._headers(),
            )
        except httpx.RequestError as exc:
            raise BrightDataError(f"Network error triggering Bright Data collection: {exc}") from exc

        self._handle_error_response(response, "trigger_collection")

        data: dict[str, Any]
        try:
            parsed = response.json()
            data = parsed if isinstance(parsed, dict) else {"collection_id": str(parsed)}
        except Exception:
            data = {"collection_id": response.text.strip().strip('"')}

        collection_id = (
            data.get("collection_id")
            or data.get("snapshot_id")
            or data.get("response_id")
            or data.get("id")
        )
        if not collection_id:
            raise BrightDataError(f"Bright Data trigger response did not contain a valid collection identifier: {data}")

        return CollectionTriggerResult(
            collection_id=str(collection_id),
            status=data.get("status", "running"),
            raw_response=data,
        )

    def get_collection_status(self, *, collection_id: str) -> CollectionProgress:
        """Check progress status of a running collection job."""
        # 1. Primary DCA check via /dca/log/{job_id}
        url_log = f"{self.base_url}/dca/log/{collection_id}"
        try:
            response = self._client.get(url_log, headers=self._headers())
            if response.status_code == 200:
                data = response.json()
                raw_status = str(data.get("status", "")).lower()
                if raw_status in {"done", "finished", "completed"}:
                    lines = int(data.get("lines", 0) or 0)
                    fails = int(data.get("fails", 0) or 0)
                    if lines > 0 or fails == 0:
                        return CollectionProgress(
                            collection_id=collection_id,
                            status="ready",
                            progress=1.0,
                            raw_response=data,
                        )
                    else:
                        return CollectionProgress(
                            collection_id=collection_id,
                            status="failed",
                            error=f"Collection completed with {fails} failure(s) and 0 output records",
                            raw_response=data,
                        )
                elif raw_status in {"running", "queueing", "queued", "pending", "started"}:
                    return CollectionProgress(
                        collection_id=collection_id,
                        status="running",
                        progress=0.5,
                        raw_response=data,
                    )
        except Exception:
            pass

        # 2. Check /dca/dataset?id={id} status code (202 Accepted = running, 200 OK = ready)
        url_dca = f"{self.base_url}/dca/dataset"
        try:
            response = self._client.get(url_dca, params={"id": collection_id}, headers=self._headers())
            if response.status_code == 202:
                return CollectionProgress(
                    collection_id=collection_id,
                    status="running",
                    progress=0.5,
                    raw_response={"status": "processing"},
                )
            elif response.status_code == 200 and len(response.content) > 0:
                return CollectionProgress(
                    collection_id=collection_id,
                    status="ready",
                    progress=1.0,
                    raw_response={"status": "ready"},
                )
        except Exception:
            pass

        # 3. Fallback to Datasets v3 progress endpoint
        url_v3 = f"{self.base_url}/datasets/v3/progress/{collection_id}"
        try:
            response = self._client.get(url_v3, headers=self._headers())
            if response.status_code == 200:
                data = response.json()
                raw_status = str(data.get("status", "running")).lower()
                progress = float(data.get("progress", 0.0) or 0.0)
                error = data.get("error") or data.get("error_message")
                return CollectionProgress(
                    collection_id=collection_id,
                    status=raw_status,
                    progress=progress,
                    error=str(error) if error else None,
                    raw_response=data,
                )
        except Exception:
            pass

        return CollectionProgress(
            collection_id=collection_id,
            status="running",
            progress=0.5,
            raw_response={"status": "running"},
        )

    def get_collection_result(
        self,
        *,
        collection_id: str,
        max_retries: int = 5,
        retry_delay: float = 2.0,
    ) -> list[dict[str, Any]] | None:
        """Retrieve structured JSON/JSONL results for a completed collection/snapshot."""
        import json
        import time

        for attempt in range(max_retries):
            # 1. Try DCA dataset endpoint
            url_dca = f"{self.base_url}/dca/dataset"
            try:
                response = self._client.get(url_dca, params={"id": collection_id}, headers=self._headers())
                if response.status_code == 200:
                    text = response.text.strip()
                    if text:
                        try:
                            data = response.json()
                            if isinstance(data, list):
                                return data
                            if isinstance(data, dict):
                                return [data]
                        except Exception:
                            # Parse JSON Lines / ndjson
                            records = []
                            for line in text.splitlines():
                                line = line.strip()
                                if line:
                                    try:
                                        records.append(json.loads(line))
                                    except Exception:
                                        pass
                            if records:
                                return records
                elif response.status_code == 202:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
            except Exception:
                pass

            # 2. Try Datasets v3 snapshot endpoint
            url_v3 = f"{self.base_url}/datasets/v3/snapshot/{collection_id}"
            try:
                response = self._client.get(
                    url_v3,
                    params={"format": "json"},
                    headers=self._headers(),
                )
                if response.status_code == 200:
                    data = response.json()
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict):
                        return [data]
                elif response.status_code == 202:
                    if attempt < max_retries - 1:
                        time.sleep(retry_delay)
                        continue
                    return None
            except Exception:
                pass

        return []



