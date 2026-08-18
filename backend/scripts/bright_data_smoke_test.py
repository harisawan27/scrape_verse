"""Real Bright Data Scraper Studio Smoke Test.

Validates authentication, collector metadata, live collection trigger,
progress polling, snapshot retrieval, and schema normalization.
NEVER prints or exposes API keys or private credentials.
"""

import os
import sys
import time
from pathlib import Path
from typing import Any

# Ensure backend path is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

import httpx
from app.config import get_settings
from app.integrations.bright_data import (
    BrightDataAuthError,
    BrightDataError,
    BrightDataNotFoundError,
    BrightDataRateLimitError,
    HttpBrightDataAdapter,
    map_bright_data_to_snapshot,
)


def run_smoke_test() -> dict[str, Any]:
    settings = get_settings()
    api_key = (
        settings.bright_data_api_key
        or os.getenv("BRIGHT_DATA_API_KEY")
        or os.getenv("BRIGHTDATA_API_KEY")
    )
    collector_id = (
        settings.bright_data_collector_id
        or os.getenv("BRIGHT_DATA_COLLECTOR_ID")
        or os.getenv("BRIGHTDATA_COLLECTOR_ID")
    )
    base_url = settings.bright_data_base_url or "https://api.brightdata.com"


    if not api_key:
        print("[ERROR] BRIGHT_DATA_API_KEY is not configured in .env", file=sys.stderr)
        return {"status": "FAILED", "error": "Missing BRIGHT_DATA_API_KEY"}

    if not collector_id:
        print("[ERROR] BRIGHT_DATA_COLLECTOR_ID is not configured in .env", file=sys.stderr)
        return {"status": "FAILED", "error": "Missing BRIGHT_DATA_COLLECTOR_ID"}

    print(f"[INFO] Initializing Bright Data adapter for base_url: {base_url}", flush=True)
    print(f"[INFO] Target Collector ID: {collector_id}", flush=True)

    # Check whether collector_id is a Scraper Studio custom collector
    is_custom_collector = collector_id.startswith("c_")
    print(f"[INFO] Collector type: {'Custom Scraper Studio (c_...)' if is_custom_collector else 'Dataset identifier (' + collector_id + ')'}", flush=True)

    adapter = HttpBrightDataAdapter(api_key=api_key, base_url=base_url, timeout_seconds=60.0)

    # 1. Trigger live collection on a public product page matching custom scraper domain
    target_url = "https://www.daraz.pk/products/m10-tws-wireless-bluetooth-earbuds-touch-control-waterproof-headsets-with-microphone-i435345719.html"
    print(f"[STEP 1] Triggering collection for safe test URL: {target_url}", flush=True)

    try:
        trigger_res = adapter.trigger_collection(
            collector_id=collector_id,
            inputs=[{"url": target_url}],
        )
    except BrightDataAuthError as exc:
        print(f"[AUTH FAILED] Authentication rejected by Bright Data API: {exc}", file=sys.stderr, flush=True)
        return {"status": "FAILED", "step": "AUTH", "error": str(exc)}
    except BrightDataNotFoundError as exc:
        print(f"[NOT FOUND] Collector ID not found: {exc}", file=sys.stderr, flush=True)
        return {"status": "FAILED", "step": "COLLECTOR_NOT_FOUND", "error": str(exc)}
    except BrightDataRateLimitError as exc:
        print(f"[RATE LIMITED] Rate limit exceeded: {exc}", file=sys.stderr, flush=True)
        return {"status": "FAILED", "step": "RATE_LIMIT", "error": str(exc)}
    except Exception as exc:
        print(f"[TRIGGER FAILED] Error triggering collection: {exc}", file=sys.stderr, flush=True)
        return {"status": "FAILED", "step": "TRIGGER", "error": str(exc)}

    snapshot_id = trigger_res.collection_id
    print(f"[STEP 1 SUCCESS] Snapshot job created. Snapshot ID: {snapshot_id}", flush=True)
    print(f"[STEP 1 STATUS] Initial Job Status: {trigger_res.status}", flush=True)

    # 2. Poll progress endpoint until terminal state (ready or failed)
    print(f"[STEP 2] Polling progress endpoint for snapshot: {snapshot_id}", flush=True)
    max_wait_seconds = 240
    poll_interval = 5.0
    start_time = time.time()
    terminal_status = None
    last_progress = None

    while (time.time() - start_time) < max_wait_seconds:
        try:
            progress_res = adapter.get_collection_status(collection_id=snapshot_id)
            status = progress_res.status.lower()
            last_progress = progress_res

            elapsed = int(time.time() - start_time)
            print(f"  [POLL {elapsed}s] Status: {status}, Progress: {progress_res.progress}", flush=True)

            if progress_res.is_ready:
                terminal_status = "ready"
                print(f"[STEP 2 SUCCESS] Snapshot is ready after {elapsed}s", flush=True)
                break
            elif progress_res.is_failed:
                terminal_status = "failed"
                print(f"[STEP 2 FAILED] Collection failed on Bright Data: {progress_res.error}", file=sys.stderr, flush=True)
                break
        except Exception as exc:
            print(f"  [POLL WARNING] Error polling status: {exc}", flush=True)

        time.sleep(poll_interval)

    if not terminal_status:
        print(f"[TIMEOUT] Snapshot {snapshot_id} did not complete within {max_wait_seconds}s", file=sys.stderr, flush=True)
        return {
            "status": "TIMEOUT",
            "snapshot_id": snapshot_id,
            "last_status": last_progress.status if last_progress else "unknown",
        }

    if terminal_status == "failed":
        return {
            "status": "COLLECTION_FAILED",
            "snapshot_id": snapshot_id,
            "error": last_progress.error if last_progress else "Unknown Bright Data error",
        }

    # 3. Retrieve structured JSON snapshot
    print(f"[STEP 3] Fetching snapshot JSON for snapshot: {snapshot_id}", flush=True)
    try:
        raw_results = adapter.get_collection_result(collection_id=snapshot_id)
    except Exception as exc:
        print(f"[FETCH FAILED] Error fetching snapshot: {exc}", file=sys.stderr, flush=True)
        return {"status": "FETCH_FAILED", "snapshot_id": snapshot_id, "error": str(exc)}

    if raw_results is None:
        print("[FETCH FAILED] Snapshot data returned None (still 202)", file=sys.stderr, flush=True)
        return {"status": "FETCH_EMPTY", "snapshot_id": snapshot_id}

    item_count = len(raw_results)
    print(f"[STEP 3 SUCCESS] Retrieved {item_count} record(s) from Bright Data snapshot.", flush=True)

    # 4. Normalize through map_bright_data_to_snapshot
    print("[STEP 4] Normalizing payload via map_bright_data_to_snapshot()", flush=True)
    normalized = map_bright_data_to_snapshot(
        raw_results,
        default_url=target_url,
        default_title="Daraz Product",
    )

    print(f"[STEP 4 SUCCESS] Normalized Snapshot Payload:", flush=True)
    print(f"  - URL: {normalized.get('url')}", flush=True)
    print(f"  - Title: {normalized.get('title')}", flush=True)
    print(f"  - Price: {normalized.get('price')}", flush=True)
    print(f"  - Currency: {normalized.get('currency')}", flush=True)
    print(f"  - Availability: {normalized.get('availability')}", flush=True)
    print(f"  - Extra Extracted Fields: {normalized.get('extracted_fields', {})}", flush=True)

    return {
        "status": "SUCCESS",
        "authentication": "PASS",
        "collector_id": collector_id,
        "is_custom_collector": is_custom_collector,
        "snapshot_id": snapshot_id,
        "raw_record_count": item_count,
        "normalized_payload": normalized,
    }


if __name__ == "__main__":
    result = run_smoke_test()
    if result.get("status") == "SUCCESS":
        print("\n=== SMOKE TEST: ALL CHECKS PASSED ===", flush=True)
        sys.exit(0)
    else:
        print(f"\n=== SMOKE TEST FAILED: {result} ===", file=sys.stderr, flush=True)
        sys.exit(1)

