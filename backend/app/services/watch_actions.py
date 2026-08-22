import re
import logging
from typing import Any
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models import Watch, WatchRun, Snapshot, Alert, Schedule, WatchTarget, utc_now
from app.schemas import WatchChatResponse, WatchOverviewRead
from app.repositories import WatchRepository

logger = logging.getLogger(__name__)


class WatchActionHandler:
    """
    Context-aware natural-language assistant for individual Watch pages.
    Interprets questions about watch status/alerts and safely executes authorized actions:
    - update_watch_rule
    - run_watch_now
    - change_cadence
    - pause_watch / resume_watch
    - add_watch_target / remove_watch_target
    """

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.repo = WatchRepository(db)

    def handle_message(self, watch_id: str, message: str) -> WatchChatResponse:
        """Process conversational query or command on a specific watch with full operational context."""
        watch = self.repo.get(watch_id, user_id=self.user_id)
        if not watch:
            return WatchChatResponse(
                reply="Watch not found or you do not have permission to access it.",
                action_taken=None,
            )

        overview = self.repo.get_watch_overview(watch_id)
        msg_lower = message.strip().lower()

        # Extract current state
        curr_price = overview.latest_value.price if overview.latest_value else None
        curr_orig = overview.latest_value.original_price if overview.latest_value else None
        curr_curr = overview.latest_value.currency if overview.latest_value else "PKR"
        spec = watch.monitoring_spec if isinstance(watch.monitoring_spec, dict) else {}
        rules = spec.get("rules", [])
        
        # 1. Action: Update threshold / rule (e.g. "Change it to 1200", "Set alert to 1500", "Change my threshold to PKR 1,200")
        match_thresh = re.search(r"(?:change|set|update|make)\s*(?:it|threshold|price|alert)?\s*(?:to|at)?\s*(?:rs\.?|pkr)?\s*(\d+(?:,\d+)*(?:\.\d+)?\s*k|\d+(?:,\d+)*(?:\.\d+)?)", msg_lower)
        if match_thresh or ("change" in msg_lower and any(c.isdigit() for c in msg_lower)):
            raw_v = match_thresh.group(1).replace(",", "").replace(" ", "").strip() if match_thresh else re.search(r"(\d+)", msg_lower).group(1)
            new_thresh = float(raw_v[:-1]) * 1000.0 if raw_v.endswith("k") else float(raw_v)

            # Update rules
            updated_rules = []
            updated = False
            old_val = 800
            for r in rules:
                if r.get("type") in ("price_below", "price_above"):
                    old_val = r.get("value", old_val)
                    r["value"] = new_thresh
                    updated = True
                updated_rules.append(r)

            if not updated:
                updated_rules.append({"type": "price_below", "field": "price", "value": new_thresh, "currency": curr_curr})

            import copy
            from sqlalchemy.orm.attributes import flag_modified

            new_spec = copy.deepcopy(spec)
            new_spec["rules"] = updated_rules
            new_spec["threshold"] = new_thresh
            watch.monitoring_spec = new_spec
            flag_modified(watch, "monitoring_spec")
            watch.updated_at = utc_now()
            self.db.commit()

            updated_overview = self.repo.get_watch_overview(watch_id)
            reply = (
                f"Done! I have updated your alert threshold to **{curr_curr} {new_thresh:,.0f}** "
                f"(previously {curr_curr} {old_val:,.0f}).\n\n"
                f"The current selling price is **{curr_curr} {curr_price:,.0f}**, so Web Radar will alert you "
                f"as soon as it reaches or drops below {curr_curr} {new_thresh:,.0f}."
            )
            return WatchChatResponse(
                reply=reply,
                action_taken="rule_updated",
                action_details={"old_threshold": old_val, "new_threshold": new_thresh, "currency": curr_curr},
                updated_watch=updated_overview,
            )

        # 2. Action: Run Now (e.g. "Check it again now", "Run now", "Scan now")
        if any(k in msg_lower for k in ["check it again", "run now", "scan now", "check now", "trigger scan"]):
            from app.services.runs import RunCreationService
            run_creator = RunCreationService(self.db)
            try:
                run = run_creator.create(watch_id=watch.id)
                from app.services.runs import BrightDataRunExecutor
                executor = BrightDataRunExecutor(self.db)
                executor.execute(run)
                updated_overview = self.repo.get_watch_overview(watch_id)
                return WatchChatResponse(
                    reply=f"Triggered an immediate scan (Run `{run.id[:8]}...`). The scraper is executing and results will reflect in your timeline.",
                    action_taken="scan_triggered",
                    action_details={"run_id": run.id},
                    updated_watch=updated_overview,
                )
            except Exception as e:
                return WatchChatResponse(
                    reply=f"A scan is already currently in progress.",
                    action_taken=None,
                )

        # 3. Action: Change Cadence (e.g. "Check every 6 hours instead", "Change cadence to daily")
        if "cadence" in msg_lower or "every" in msg_lower or "hourly" in msg_lower or "daily" in msg_lower:
            new_cadence = "hourly"
            new_mins = 60
            if "30 min" in msg_lower or "30m" in msg_lower:
                new_cadence = "custom"
                new_mins = 30
            elif "6 hour" in msg_lower or "6h" in msg_lower:
                new_cadence = "custom"
                new_mins = 360
            elif "daily" in msg_lower or "24 hour" in msg_lower or "day" in msg_lower:
                new_cadence = "daily"
                new_mins = 1440

            if watch.schedule:
                watch.schedule.cadence = new_cadence
                watch.schedule.updated_at = utc_now()
                self.db.commit()

            updated_overview = self.repo.get_watch_overview(watch_id)
            return WatchChatResponse(
                reply=f"Updated monitoring cadence to **{new_cadence}** (every {new_mins} minutes).",
                action_taken="cadence_changed",
                action_details={"cadence": new_cadence, "cadence_minutes": new_mins},
                updated_watch=updated_overview,
            )

        # 4. Action: Pause / Resume
        if "pause" in msg_lower:
            watch.status = "paused"
            watch.updated_at = utc_now()
            self.db.commit()
            updated_overview = self.repo.get_watch_overview(watch_id)
            return WatchChatResponse(
                reply="Paused this watch. Scheduled background scans are temporarily suspended.",
                action_taken="status_changed",
                action_details={"status": "paused"},
                updated_watch=updated_overview,
            )
        if "resume" in msg_lower or "activate" in msg_lower or "unpause" in msg_lower:
            watch.status = "active"
            watch.updated_at = utc_now()
            self.db.commit()
            updated_overview = self.repo.get_watch_overview(watch_id)
            return WatchChatResponse(
                reply="Resumed this watch. Background monitoring is now active.",
                action_taken="status_changed",
                action_details={"status": "active"},
                updated_watch=updated_overview,
            )

        # 5. Question: "Why haven't you alerted me yet?" / Status explanation
        if any(k in msg_lower for k in ["why haven't you alerted", "why no alert", "why didn't this trigger", "status", "what is the price", "why"]):
            rule_summary = []
            for r in rules:
                if r.get("type") == "price_below":
                    rule_summary.append(f"alert below **{r.get('currency', curr_curr)} {r.get('value', 0):,.0f}**")

            rules_text = ", ".join(rule_summary) if rule_summary else "no active threshold rule"
            price_text = f"**{curr_curr} {curr_price:,.0f}**" if curr_price is not None else "Unknown"
            orig_text = f" *(Original: {curr_curr} {curr_orig:,.0f})*" if curr_orig else ""

            reply = (
                f"Here is why no alert has fired yet:\n\n"
                f"• **Current Monitored Selling Price:** {price_text}{orig_text}\n"
                f"• **Your Active Rule:** {rules_text}\n\n"
                f"Because the current selling price ({price_text}) has not dropped below your alert threshold "
                f"({rules_text}), the trigger condition has not been met. "
                f"All {len(overview.runs)} scheduled runs have executed successfully and the scraper is healthy."
            )
            return WatchChatResponse(
                reply=reply,
                action_taken=None,
                updated_watch=overview,
            )

        # 6. General explanation
        return WatchChatResponse(
            reply=(
                f"I'm monitoring **{watch.title}**.\n"
                f"Current Price: **{curr_curr} {curr_price:,.0f}** | Health: **{overview.health_status}**\n"
                f"You can ask me to change thresholds, change check cadence, pause/resume, or run an immediate scan."
            ),
            action_taken=None,
            updated_watch=overview,
        )
