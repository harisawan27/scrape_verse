from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Change, Snapshot, Watch, WatchRun, utc_now
from app.services.changes import diff_payloads


ACTIVE_RUN_STATES = {"pending", "running"}
TERMINAL_RUN_STATES = {"succeeded", "failed"}


class RunServiceError(Exception):
    pass


class WatchNotFoundError(RunServiceError):
    pass


class WatchNotEligibleError(RunServiceError):
    pass


class ActiveRunExistsError(RunServiceError):
    pass


class RunNotExecutableError(RunServiceError):
    pass


class RunCreationService:
    """Creates durable pending Runs before any provider execution can begin."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, watch_id: str, *, scheduled_for: datetime | None = None) -> WatchRun:
        watch = self.db.get(Watch, watch_id)
        if watch is None:
            raise WatchNotFoundError(f"watch {watch_id} does not exist")
        if watch.status != "active":
            raise WatchNotEligibleError(f"watch {watch_id} is not active")

        active_run = self.db.scalar(
            select(WatchRun.id).where(WatchRun.watch_id == watch_id, WatchRun.status.in_(ACTIVE_RUN_STATES))
        )
        if active_run is not None:
            raise ActiveRunExistsError(f"watch {watch_id} already has an active run")

        run = WatchRun(watch_id=watch_id, scheduled_for=scheduled_for or utc_now(), status="pending")
        self.db.add(run)
        try:
            self.db.commit()
        except IntegrityError as exc:
            self.db.rollback()
            # The partial unique index closes the race between the pre-check and insert.
            raise ActiveRunExistsError(f"watch {watch_id} already has an active run") from exc
        self.db.refresh(run)
        return run


def get_previous_successful_snapshot(db: Session, run: WatchRun) -> Snapshot | None:
    statement = (
        select(Snapshot)
        .join(WatchRun, Snapshot.run_id == WatchRun.id)
        .where(
            WatchRun.watch_id == run.watch_id,
            WatchRun.status == "succeeded",
            WatchRun.id != run.id,
        )
        .order_by(Snapshot.captured_at.desc(), Snapshot.created_at.desc())
        .limit(1)
    )
    return db.scalar(statement)


class MockRunExecutor:
    """Deterministic local executor; it deliberately has no Bright Data dependency."""

    def __init__(self, db: Session):
        self.db = db

    def execute(
        self,
        run: WatchRun,
        *,
        payload: dict[str, Any] | None = None,
        fail: bool = False,
    ) -> WatchRun:
        persisted_run = self.db.get(WatchRun, run.id)
        if persisted_run is None or persisted_run.status != "pending":
            raise RunNotExecutableError("only pending runs can be executed")

        persisted_run.status = "running"
        persisted_run.started_at = utc_now()
        self.db.commit()

        try:
            watch = self.db.get(Watch, persisted_run.watch_id)
            if watch is None:
                raise RuntimeError("watch was deleted before execution")
            if fail:
                raise RuntimeError("mock extraction failed")

            extracted_payload = payload or self._payload_for(watch)
            previous = get_previous_successful_snapshot(self.db, persisted_run)
            snapshot = Snapshot(
                run_id=persisted_run.id,
                watch_id=watch.id,
                payload=extracted_payload,
                metadata_={"source": "mock", "format": "structured-json"},
                captured_at=utc_now(),
            )
            self.db.add(snapshot)

            if previous is not None:
                for change_type, details in diff_payloads(previous.payload, extracted_payload):
                    self.db.add(
                        Change(
                            watch_id=watch.id,
                            run_id=persisted_run.id,
                            change_type=change_type,
                            details=details,
                        )
                    )

            persisted_run.status = "succeeded"
            persisted_run.finished_at = utc_now()
            self.db.commit()
        except Exception as exc:
            self.db.rollback()
            failed_run = self.db.get(WatchRun, run.id)
            if failed_run is not None:
                failed_run.status = "failed"
                failed_run.finished_at = utc_now()
                failed_run.error_code = "mock_execution_failed"
                failed_run.error_detail = str(exc)
                self.db.commit()
            return failed_run  # type: ignore[return-value]

        self.db.refresh(persisted_run)
        return persisted_run

    @staticmethod
    def _payload_for(watch: Watch) -> dict[str, Any]:
        spec = watch.monitoring_spec
        return {
            "url": watch.url,
            "title": watch.title,
            "price": spec.get("mock_price", spec.get("value", 0)),
            "currency": spec.get("currency", "PKR"),
        }


class BrightDataRunExecutor:
    """Asynchronous, restart-safe executor backed by Bright Data Scraper Studio."""

    def __init__(
        self,
        db: Session,
        adapter: Any | None = None,
        default_collector_id: str | None = None,
    ):
        from app.config import get_settings
        from app.integrations.bright_data import HttpBrightDataAdapter, MockBrightDataAdapter

        self.db = db
        settings = get_settings()
        if adapter is not None:
            self.adapter = adapter
        elif settings.bright_data_api_key:
            self.adapter = HttpBrightDataAdapter(
                api_key=settings.bright_data_api_key,
                base_url=settings.bright_data_base_url,
            )
        else:
            self.adapter = MockBrightDataAdapter()

        self.default_collector_id = default_collector_id or settings.bright_data_collector_id

    def execute(self, run: WatchRun) -> WatchRun:
        persisted_run = self.db.get(WatchRun, run.id)
        if persisted_run is None:
            raise RunNotExecutableError("run does not exist")

        if persisted_run.status in TERMINAL_RUN_STATES:
            # Idempotent no-op for finished runs
            return persisted_run

        watch = self.db.get(Watch, persisted_run.watch_id)
        if watch is None:
            persisted_run.status = "failed"
            persisted_run.finished_at = utc_now()
            persisted_run.error_code = "watch_not_found"
            persisted_run.error_detail = "Watch was deleted before execution"
            self.db.commit()
            return persisted_run

        spec = watch.monitoring_spec if isinstance(watch.monitoring_spec, dict) else {}
        collector_id = (
            spec.get("scraper_id")
            or spec.get("collector_id")
            or self.default_collector_id
        )
        if not collector_id:
            persisted_run.status = "failed"
            persisted_run.finished_at = utc_now()
            persisted_run.error_code = "missing_collector_id"
            persisted_run.error_detail = "No Scraper Studio collector configured for watch"
            self.db.commit()
            return persisted_run


        # Step 1: If pending, initiate collection on Bright Data and persist collection ID immediately
        if persisted_run.status == "pending":
            persisted_run.status = "running"
            persisted_run.started_at = utc_now()
            try:
                trigger_res = self.adapter.trigger_collection(
                    collector_id=collector_id,
                    inputs=[{"url": watch.url}],
                )
                persisted_run.bright_data_collection_id = trigger_res.collection_id
                self.db.commit()
            except Exception as exc:
                self.db.rollback()
                failed_run = self.db.get(WatchRun, run.id)
                if failed_run is not None:
                    from app.integrations.bright_data import BrightDataAuthError, BrightDataNotFoundError
                    error_code = "bright_data_trigger_failed"
                    if isinstance(exc, BrightDataAuthError):
                        error_code = "bright_data_auth_failed"
                    elif isinstance(exc, BrightDataNotFoundError):
                        error_code = "bright_data_collector_not_found"

                    failed_run.status = "failed"
                    failed_run.finished_at = utc_now()
                    failed_run.error_code = error_code
                    failed_run.error_detail = str(exc)
                    self.db.commit()
                    return failed_run
                raise

        # Step 2: If running and has external collection ID, poll status and finalize if ready
        if persisted_run.status == "running" and persisted_run.bright_data_collection_id:
            try:
                progress = self.adapter.get_collection_status(
                    collection_id=persisted_run.bright_data_collection_id
                )
            except Exception as exc:
                # Polling error: leave running for next tick, do not fail permanently
                return persisted_run

            if progress.is_failed:
                persisted_run.status = "failed"
                persisted_run.finished_at = utc_now()
                persisted_run.error_code = "bright_data_collection_failed"
                persisted_run.error_detail = progress.error or "Bright Data collection reported failure"
                self.db.commit()
                return persisted_run

            if progress.is_ready:
                from app.integrations.bright_data import map_bright_data_to_snapshot

                raw_data = self.adapter.get_collection_result(
                    collection_id=persisted_run.bright_data_collection_id
                )
                if not raw_data:
                    persisted_run.status = "failed"
                    persisted_run.finished_at = utc_now()
                    persisted_run.error_code = "bright_data_empty_result"
                    persisted_run.error_detail = "Bright Data completed but returned 0 records"
                    self.db.commit()
                    return persisted_run

                normalized_payload = map_bright_data_to_snapshot(
                    raw_data,
                    default_url=watch.url,
                    default_title=watch.title,
                )

                # Persist exactly one snapshot for this run
                existing_snapshot = self.db.scalar(
                    select(Snapshot).where(Snapshot.run_id == persisted_run.id)
                )
                if existing_snapshot is None:
                    snapshot = Snapshot(
                        run_id=persisted_run.id,
                        watch_id=watch.id,
                        payload=normalized_payload,
                        metadata_={
                            "source": "bright_data",
                            "collector_id": collector_id,
                            "collection_id": persisted_run.bright_data_collection_id,
                        },
                        captured_at=utc_now(),
                    )
                    self.db.add(snapshot)

                    previous = get_previous_successful_snapshot(self.db, persisted_run)
                    if previous is not None:
                        for change_type, details in diff_payloads(previous.payload, normalized_payload):
                            self.db.add(
                                Change(
                                    watch_id=watch.id,
                                    run_id=persisted_run.id,
                                    change_type=change_type,
                                    details=details,
                                )
                            )

                persisted_run.status = "succeeded"
                persisted_run.finished_at = utc_now()
                self.db.commit()
                self.db.refresh(persisted_run)
                return persisted_run

        return persisted_run

