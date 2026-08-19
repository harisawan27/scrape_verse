"""Real Google Gemini Natural-Language Watch Planner Smoke Test.

Validates that configured Gemini API credentials can generate structured
planner outputs conforming to Web Radar's schema.
NEVER prints or exposes API keys or private credentials.
"""

import os
import sys
from pathlib import Path

# Ensure backend path is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from app.config import get_settings
from app.integrations.llm import GeminiPlannerClient
from app.services.planner import NaturalLanguageWatchPlanner


def run_gemini_smoke_test() -> int:
    settings = get_settings()
    api_key = settings.gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key:
        print("[SKIP] GEMINI_API_KEY is not configured in .env. Skipping live smoke test.")
        return 0

    print(f"[INFO] Initializing GeminiPlannerClient with model: {settings.gemini_model_name}")
    client = GeminiPlannerClient(
        api_key=api_key,
        model_name=settings.gemini_model_name,
        base_url=settings.gemini_base_url,
    )
    planner = NaturalLanguageWatchPlanner(llm_client=client)

    test_message = "Watch this Daraz gaming chair every 30 minutes and alert me when it drops below Rs 4,500 or comes back in stock."
    test_url = "https://www.daraz.pk/products/ergonomic-gaming-chair-i998877.html"

    print(f"[STEP 1] Generating plan for message:\n  '{test_message}'\n  URL: {test_url}")
    try:
        preview = planner.preview_plan(message=test_message, url=test_url)
    except Exception as exc:
        print(f"[ERROR] Live Gemini planner call failed: {exc}", file=sys.stderr)
        return 1

    print(f"[STEP 1 RESULT] Status: {preview.status}")
    if preview.status != "ready" or preview.plan is None:
        print(f"[ERROR] Expected status 'ready', got '{preview.status}': {preview.message}", file=sys.stderr)
        return 1

    plan = preview.plan
    print(f"[STEP 1 SUCCESS] Validated Plan:")
    print(f"  - Target URL: {plan.url}")
    print(f"  - Cadence: {plan.schedule.cadence} ({plan.schedule.cadence_minutes} minutes, tz: {plan.schedule.timezone})")
    print(f"  - Collector ID: {plan.collector_id}")
    print(f"  - Rules Count: {len(plan.monitoring_spec.get('rules', []))}")
    for idx, rule in enumerate(plan.monitoring_spec.get("rules", []), 1):
        print(f"    Rule {idx}: type={rule.get('type')}, field={rule.get('field')}, value={rule.get('value')}, currency={rule.get('currency')}")

    print("\n=== GEMINI PLANNER SMOKE TEST: PASSED ===")
    return 0


if __name__ == "__main__":
    sys.exit(run_gemini_smoke_test())
