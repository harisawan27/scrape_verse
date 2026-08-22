from datetime import datetime
from typing import Any
from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    Alert,
    Change,
    Conversation,
    ConversationMessage,
    ScraperRepair,
    Schedule,
    Snapshot,
    User,
    Watch,
    WatchRun,
    WatchTarget,
    utc_now,
)
from app.schemas import (
    ActivityEventRead,
    AlertRead,
    ScraperRepairRead,
    SnapshotRead,
    UserCreate,
    WatchCreate,
    WatchOverviewRead,
    WatchOverviewStats,
    WatchRead,
    WatchRunRead,
    WatchSummaryRead,
    WatchUpdate,
)
from app.services.overview import (
    derive_health_status,
    extract_domain,
    extract_product_current_value,
    resolve_cadence_minutes,
)
from app.services.scheduler import calculate_next_due_at, utc_now


class WatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data: UserCreate, auth_id: str | None = None) -> User:
        user = User(email=data.email, auth_id=auth_id or data.auth_id)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user


    def get_user(self, user_id: str) -> User | None:
        user = self.db.get(User, user_id)
        if user is not None:
            return user
        # Check by auth_id
        user = self.db.scalar(select(User).where(User.auth_id == str(user_id)))
        if user is not None:
            return user
        # Auto-provision if user exists in neon_auth.user
        try:
            query = text('SELECT id::text, email FROM neon_auth.user WHERE id::text = :uid OR email = :uid LIMIT 1')
            row = self.db.execute(query, {"uid": str(user_id)}).first()
            if row:
                from app.auth import resolve_or_create_user
                return resolve_or_create_user(self.db, str(row[0]), str(row[1]))
        except Exception:
            pass
        return None

    def get_user_by_email(self, email: str) -> User | None:
        return self.db.scalar(select(User).where(User.email == email))

    def get_user_watch(self, user_id: str, watch_id: str) -> Watch | None:
        return self.get(watch_id, user_id=user_id)

    def create(self, data: WatchCreate) -> Watch:
        watch = Watch(
            user_id=data.user_id,
            url=str(data.url),
            title=data.title,
            instruction=data.instruction,
            monitoring_spec=data.monitoring_spec,
            status=data.status,
        )
        watch.schedule = Schedule(**data.schedule.model_dump())
        self.db.add(watch)
        self.db.commit()
        return self.get(watch.id)  # type: ignore[return-value]

    def get(self, watch_id: str, user_id: str | None = None) -> Watch | None:
        statement = select(Watch).options(joinedload(Watch.schedule)).where(Watch.id == watch_id)
        if user_id is not None:
            user = self.get_user(user_id)
            target_uid = user.id if user else user_id
            statement = statement.where((Watch.user_id == target_uid) | (Watch.user_id == user_id))
        return self.db.scalar(statement)

    def list_for_user(self, user_id: str) -> list[Watch]:
        user = self.get_user(user_id)
        target_uid = user.id if user else user_id
        statement = (
            select(Watch)
            .options(joinedload(Watch.schedule))
            .where((Watch.user_id == target_uid) | (Watch.user_id == user_id))
            .order_by(Watch.created_at.desc())
        )
        return list(self.db.scalars(statement).unique())

    def update(self, watch: Watch, data: WatchUpdate) -> Watch:
        values = data.model_dump(exclude_unset=True, exclude={"schedule"})
        if "url" in values and values["url"] is not None:
            values["url"] = str(values["url"])

        # Sync watch status with schedule.enabled
        if "status" in values:
            if values["status"] == "active":
                if watch.schedule:
                    watch.schedule.enabled = True
            elif values["status"] in ("paused", "archived"):
                if watch.schedule:
                    watch.schedule.enabled = False

        for field, value in values.items():
            setattr(watch, field, value)

        if data.schedule is not None and watch.schedule is not None:
            schedule_values = data.schedule.model_dump(exclude_unset=True)
            cadence_changed = "cadence" in schedule_values and schedule_values["cadence"] != watch.schedule.cadence
            tz_changed = "timezone" in schedule_values and schedule_values["timezone"] != watch.schedule.timezone

            for field, value in schedule_values.items():
                setattr(watch.schedule, field, value)

            # If cadence/timezone changed without explicit next_due_at, recalibrate next_due_at
            if (cadence_changed or tz_changed) and "next_due_at" not in schedule_values:
                watch.schedule.next_due_at = calculate_next_due_at(
                    utc_now(),
                    cadence=watch.schedule.cadence,
                    tz_name=watch.schedule.timezone,
                )


        self.db.commit()
        return self.get(watch.id)  # type: ignore[return-value]

    def delete(self, watch: Watch) -> None:
        self.db.delete(watch)
        self.db.commit()

    def get_run(self, run_id: str) -> WatchRun | None:
        statement = (
            select(WatchRun)
            .options(
                joinedload(WatchRun.snapshot),
                joinedload(WatchRun.changes),
                joinedload(WatchRun.alerts),
                joinedload(WatchRun.repair),
            )
            .where(WatchRun.id == run_id)
        )
        return self.db.scalar(statement)

    def list_runs_for_watch(self, watch_id: str, limit: int = 50) -> list[WatchRun]:
        statement = (
            select(WatchRun)
            .options(
                joinedload(WatchRun.snapshot),
                joinedload(WatchRun.changes),
                joinedload(WatchRun.alerts),
                joinedload(WatchRun.repair),
            )
            .where(WatchRun.watch_id == watch_id)
            .order_by(WatchRun.scheduled_for.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).unique())

    def list_changes_for_watch(self, watch_id: str, limit: int = 50) -> list[Change]:
        statement = (
            select(Change)
            .where(Change.watch_id == watch_id)
            .order_by(Change.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list_alerts_for_watch(self, watch_id: str, limit: int = 50) -> list[Alert]:
        statement = (
            select(Alert)
            .where(Alert.watch_id == watch_id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def list_repairs_for_watch(self, watch_id: str, limit: int = 50) -> list[ScraperRepair]:
        statement = (
            select(ScraperRepair)
            .where(ScraperRepair.watch_id == watch_id)
            .order_by(ScraperRepair.created_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def get_latest_successful_snapshot(self, watch_id: str) -> Snapshot | None:
        """Fetch the most recent Snapshot produced by a successful run for this Watch."""
        statement = (
            select(Snapshot)
            .join(WatchRun, Snapshot.run_id == WatchRun.id)
            .where(Snapshot.watch_id == watch_id, WatchRun.status.in_(["succeeded", "success"]))
            .order_by(Snapshot.captured_at.desc())
            .limit(1)
        )
        return self.db.scalar(statement)

    def build_watch_summary(self, watch: Watch) -> WatchSummaryRead:
        """Construct the rich WatchSummaryRead card for list views."""
        from app.services.self_healing import reconcile_watch_repairs
        reconcile_watch_repairs(self.db, watch.id)

        runs = self.list_runs_for_watch(watch.id, limit=10)
        repairs = self.list_repairs_for_watch(watch.id, limit=5)
        latest_snapshot = self.get_latest_successful_snapshot(watch.id)
        alerts = self.list_alerts_for_watch(watch.id, limit=1)

        health_status = derive_health_status(watch, runs, repairs)
        latest_value = extract_product_current_value(latest_snapshot)

        latest_run_at = runs[0].scheduled_for or runs[0].created_at if runs else None
        successful_runs = [r for r in runs if r.status in ("succeeded", "success")]
        latest_successful_run_at = (
            successful_runs[0].finished_at or successful_runs[0].scheduled_for if successful_runs else None
        )

        active_repairs = [r for r in repairs if r.status in ("pending", "in_progress", "pending_answer")]
        active_repair_id = active_repairs[0].id if active_repairs else None

        latest_event = AlertRead.model_validate(alerts[0]) if alerts else None

        return WatchSummaryRead(
            id=watch.id,
            user_id=watch.user_id,
            url=watch.url,
            domain=extract_domain(watch.url),
            title=watch.title,
            instruction=watch.instruction,
            status=watch.status,
            health_status=health_status,
            cadence=watch.schedule.cadence if watch.schedule else "hourly",
            cadence_minutes=resolve_cadence_minutes(watch),
            timezone=watch.schedule.timezone if watch.schedule else "UTC",
            next_due_at=watch.schedule.next_due_at if watch.schedule else None,
            created_at=watch.created_at,
            updated_at=watch.updated_at,
            latest_run_at=latest_run_at,
            latest_successful_run_at=latest_successful_run_at,
            latest_value=latest_value,
            latest_event=latest_event,
            active_repair_id=active_repair_id,
        )

    def list_summaries_for_user(self, user_id: str) -> list[WatchSummaryRead]:
        """Return list of enriched WatchSummaryRead cards for all user Watches."""
        watches = self.list_for_user(user_id)
        return [self.build_watch_summary(w) for w in watches]

    def get_watch_overview(self, watch_id: str, user_id: str | None = None) -> WatchOverviewRead | None:
        """Construct the aggregate WatchOverviewRead for detail view."""
        watch = self.get(watch_id, user_id=user_id)
        if watch is None:
            return None

        from app.services.self_healing import reconcile_watch_repairs
        reconcile_watch_repairs(self.db, watch.id)

        runs = self.list_runs_for_watch(watch.id, limit=20)
        repairs = self.list_repairs_for_watch(watch.id, limit=10)
        latest_snapshot = self.get_latest_successful_snapshot(watch.id)
        alerts = self.list_alerts_for_watch(watch.id, limit=10)

        health_status = derive_health_status(watch, runs, repairs)
        latest_value = extract_product_current_value(latest_snapshot)

        # Count run statistics
        total_runs_count = self.db.scalar(
            select(func.count(WatchRun.id)).where(WatchRun.watch_id == watch_id)
        ) or 0
        successful_runs_count = self.db.scalar(
            select(func.count(WatchRun.id)).where(WatchRun.watch_id == watch_id, WatchRun.status.in_(["succeeded", "success"]))
        ) or 0
        failed_runs_count = self.db.scalar(
            select(func.count(WatchRun.id)).where(WatchRun.watch_id == watch_id, WatchRun.status == "failed")
        ) or 0

        total_events_count = self.db.scalar(
            select(func.count(Alert.id)).where(Alert.watch_id == watch_id)
        ) or 0

        stats = WatchOverviewStats(
            total_runs=total_runs_count,
            successful_runs=successful_runs_count,
            failed_runs=failed_runs_count,
            total_events=total_events_count,
        )

        active_repairs = [r for r in repairs if r.status in ("pending", "in_progress")]
        active_repair = ScraperRepairRead.model_validate(active_repairs[0]) if active_repairs else (
            ScraperRepairRead.model_validate(repairs[0]) if repairs else None
        )

        runs_read = [WatchRunRead.model_validate(r) for r in runs]
        alerts_read = [AlertRead.model_validate(a) for a in alerts]
        latest_run = runs_read[0] if runs_read else None
        latest_event = alerts_read[0] if alerts_read else None
        snapshot_read = SnapshotRead.model_validate(latest_snapshot) if latest_snapshot else None

        return WatchOverviewRead(
            watch=WatchRead.model_validate(watch),
            health_status=health_status,
            latest_snapshot=snapshot_read,
            latest_run=latest_run,
            runs=runs_read,
            latest_event=latest_event,
            alerts=alerts_read,
            active_repair=active_repair,
            latest_value=latest_value,
            stats=stats,
        )

    def list_activity_for_user(self, user_id: str, limit: int = 50) -> list[ActivityEventRead]:
        """Cross-Watch activity feed returning recent semantic events across user Watches."""
        statement = (
            select(Alert, Watch.title, Watch.url)
            .join(Watch, Alert.watch_id == Watch.id)
            .where(Watch.user_id == user_id)
            .order_by(Alert.created_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(statement).all()

        activity: list[ActivityEventRead] = []
        for alert, watch_title, watch_url in rows:
            activity.append(
                ActivityEventRead(
                    id=alert.id,
                    watch_id=alert.watch_id,
                    watch_title=watch_title,
                    watch_url=watch_url,
                    event_type=alert.event_type,
                    summary=alert.summary,
                    created_at=alert.created_at,
                    details=alert.details or {},
                )
            )
        return activity

    # --- Conversational Intelligence Repositories ---

    def create_conversation(self, user_id: str, title: str = "New Task") -> Conversation:
        conversation = Conversation(
            user_id=user_id,
            title=title,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        return conversation

    def get_conversation(self, conversation_id: str, user_id: str | None = None) -> Conversation | None:
        statement = select(Conversation).where(Conversation.id == conversation_id)
        if user_id:
            statement = statement.where(Conversation.user_id == user_id)
        return self.db.scalar(statement)

    def list_conversations_for_user(self, user_id: str, limit: int = 50) -> list[Conversation]:
        statement = (
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
        )
        return list(self.db.scalars(statement).all())

    def delete_conversation(self, conversation_id: str, user_id: str) -> bool:
        conversation = self.get_conversation(conversation_id, user_id=user_id)
        if not conversation:
            return False
        self.db.delete(conversation)
        self.db.commit()
        return True

    def add_conversation_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        message_type: str = "user",
        metadata: dict[str, Any] | None = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            message_type=message_type,
            metadata_=metadata or {},
        )
        self.db.add(msg)
        # Update conversation updated_at
        conversation = self.db.get(Conversation, conversation_id)
        if conversation:
            conversation.updated_at = utc_now()
        self.db.commit()
        self.db.refresh(msg)
        return msg

    # --- Watch Targets Repositories ---

    def list_targets_for_watch(self, watch_id: str) -> list[WatchTarget]:
        statement = (
            select(WatchTarget)
            .where(WatchTarget.watch_id == watch_id)
            .order_by(WatchTarget.created_at.asc())
        )
        return list(self.db.scalars(statement).all())

    def add_watch_target(
        self,
        watch_id: str,
        url: str,
        target_type: str = "primary",
        source_confidence: float = 1.0,
    ) -> WatchTarget:
        target = WatchTarget(
            watch_id=watch_id,
            url=url,
            target_type=target_type,
            source_confidence=source_confidence,
            enabled=True,
        )
        self.db.add(target)
        self.db.commit()
        self.db.refresh(target)
        return target

    def remove_watch_target(self, watch_id: str, target_id: str) -> bool:
        target = self.db.get(WatchTarget, target_id)
        if not target or target.watch_id != watch_id:
            return False
        self.db.delete(target)
        self.db.commit()
        return True

