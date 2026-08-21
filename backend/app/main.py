from contextlib import asynccontextmanager
import logging
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    get_current_user,
    get_optional_user,
)
from app.config import get_settings
from app.db import check_database_connection, get_db
from app.models import User
from app.repositories import WatchRepository
from app.schemas import (
    ActivityEventRead,
    AlertRead,
    ChangeRead,
    ScraperRepairRead,
    UserCreate,
    UserRead,
    WatchCreate,
    WatchCreateFromPlanRequest,

    WatchOverviewRead,
    WatchPlanPreviewRequest,
    WatchPlanPreviewResponse,
    WatchRead,
    WatchRunRead,
    WatchSummaryRead,
    WatchUpdate,
)
from app.services.planner import NaturalLanguageWatchPlanner
from app.services.runs import (
    ActiveRunExistsError,
    BrightDataRunExecutor,
    MockRunExecutor,
    RunCreationService,
    WatchNotEligibleError,
    WatchNotFoundError,
)
from app.services.scheduler import AsyncSchedulerRunner

settings = get_settings()
logger = logging.getLogger("webradar")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Configure structured logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger.info(
        "Initializing Web Radar (env=%s, scheduler=%s, interval=%.1fs)",
        settings.app_env,
        settings.scheduler_enabled,
        settings.scheduler_poll_interval_seconds,
    )

    # 2. Start background scheduler if enabled
    runner: AsyncSchedulerRunner | None = None
    if settings.scheduler_enabled:
        runner = AsyncSchedulerRunner(
            poll_interval_seconds=settings.scheduler_poll_interval_seconds,
        )
        await runner.start()
        logger.info("Autonomous background scheduler loop started")

    yield

    # 3. Graceful shutdown
    if runner:
        logger.info("Gracefully stopping autonomous background scheduler loop...")
        await runner.stop()
        logger.info("Scheduler loop stopped")


app = FastAPI(
    title="Web Radar API",
    version="0.1.0",
    description="Autonomous web monitoring backed by Bright Data Scraper Studio & Neon PostgreSQL",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins) if isinstance(settings.cors_origins, list) else [str(settings.cors_origins)],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check; intentionally fast and does not establish a database connection."""
    return {"status": "ok"}


@app.get("/health/database")
def database_health() -> dict[str, str]:
    """Readiness check for Neon/PostgreSQL; returns no connection details."""
    try:
        check_database_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "available"}


# ==========================================
# Authentication & User Identity Routes
# ==========================================

@app.get("/v1/auth/me", response_model=UserRead)
def get_me(current_user: User = Depends(get_current_user)):
    """Return the domain profile of the currently authenticated Neon Auth user."""
    return UserRead.model_validate(current_user)


@app.post("/v1/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    try:
        user = repository.create_user(data)
        logger.info("User created: %s (%s)", user.id, user.email)
        return user
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already exists") from exc



@app.post("/v1/users/ensure", response_model=UserRead)
def ensure_user(data: UserCreate, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    existing = repository.get_user_by_email(data.email)
    if existing is not None:
        return existing
    try:
        user = repository.create_user(data)
        logger.info("Demo user ensured: %s (%s)", user.id, user.email)
        return user
    except IntegrityError:
        db.rollback()
        existing = repository.get_user_by_email(data.email)
        if existing is not None:
            return existing
        raise HTTPException(status_code=500, detail="could not ensure user")


# ==========================================
# User-Scoped Watch Management
# ==========================================

@app.post("/v1/watches", response_model=WatchRead, status_code=status.HTTP_201_CREATED)
def create_watch(
    data: WatchCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    data.user_id = current_user.id
    watch = repository.create(data)
    logger.info("Watch created: %s ('%s') for user %s", watch.id, watch.title, current_user.id)
    return watch





@app.get("/v1/watches", response_model=list[WatchSummaryRead])
def list_watches(
    user_id: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Always scope results to the authenticated user
    return WatchRepository(db).list_summaries_for_user(current_user.id)


@app.get("/v1/watches/{watch_id}", response_model=WatchRead)
def get_watch(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    watch = WatchRepository(db).get(watch_id, user_id=current_user.id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return watch


@app.get("/v1/watches/{watch_id}/overview", response_model=WatchOverviewRead)
def get_watch_overview(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    overview = WatchRepository(db).get_watch_overview(watch_id, user_id=current_user.id)
    if overview is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return overview


@app.get("/v1/activity", response_model=list[ActivityEventRead])
def list_activity(
    user_id: str | None = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Strictly scoped to current user's Watches
    return WatchRepository(db).list_activity_for_user(current_user.id, limit=limit)


@app.patch("/v1/watches/{watch_id}", response_model=WatchRead)
def update_watch(
    watch_id: str,
    data: WatchUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    watch = repository.get(watch_id, user_id=current_user.id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    updated = repository.update(watch, data)
    logger.info("Watch updated: %s (status=%s)", watch.id, updated.status)
    return updated


@app.delete("/v1/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    repository = WatchRepository(db)
    watch = repository.get(watch_id, user_id=current_user.id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    repository.delete(watch)
    logger.info("Watch deleted: %s", watch_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ==========================================
# Watch Runs, Changes & Lifecycle Routes
# ==========================================

@app.post("/v1/watches/{watch_id}/runs", response_model=WatchRunRead, status_code=status.HTTP_201_CREATED)
def trigger_watch_run(
    watch_id: str,
    execute_now: bool = True,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a durable pending Run for user's Watch, then execute it via BrightData or Mock executor."""
    repository = WatchRepository(db)
    watch = repository.get(watch_id, user_id=current_user.id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")

    creation_service = RunCreationService(db)
    try:
        run = creation_service.create(watch_id)
    except WatchNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WatchNotEligibleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ActiveRunExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if execute_now:
        executor = MockRunExecutor(db)
        run = executor.execute(run)
        logger.info("Run %s executed (status=%s)", run.id, run.status)

    return repository.get_run(run.id)


@app.get("/v1/watches/{watch_id}/runs", response_model=list[WatchRunRead])
def list_watch_runs(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    if repository.get(watch_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_runs_for_watch(watch_id)


@app.get("/v1/runs/{run_id}", response_model=WatchRunRead)
def get_run(
    run_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    run = repository.get_run(run_id)
    if run is None or repository.get(run.watch_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/v1/watches/{watch_id}/changes", response_model=list[ChangeRead])
def list_watch_changes(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    if repository.get(watch_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_changes_for_watch(watch_id)


@app.get("/v1/watches/{watch_id}/events", response_model=list[AlertRead])
@app.get("/v1/watches/{watch_id}/alerts", response_model=list[AlertRead])
def list_watch_events(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    if repository.get(watch_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_alerts_for_watch(watch_id)


@app.get("/v1/watches/{watch_id}/repairs", response_model=list[ScraperRepairRead])
def list_watch_repairs(
    watch_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    if repository.get(watch_id, user_id=current_user.id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_repairs_for_watch(watch_id)


# ==========================================
# Scheduler & Natural Language Planner
# ==========================================

@app.post("/v1/scheduler/tick", response_model=list[WatchRunRead])
def run_scheduler_tick(db: Session = Depends(get_db)):
    """Trigger: Discovers and executes all currently due Watches across the system."""
    from app.services.scheduler import SchedulerService

    scheduler = SchedulerService(db)
    runs = scheduler.tick()
    repository = WatchRepository(db)
    logger.info("Manual scheduler tick executed %d run(s)", len(runs))
    return [repository.get_run(r.id) for r in runs if repository.get_run(r.id) is not None]


@app.get("/v1/scheduler/status")
def get_scheduler_status():
    return {
        "status": "ready",
        "poll_interval_seconds": settings.scheduler_poll_interval_seconds,
        "scheduler_enabled": settings.scheduler_enabled,
    }


@app.post("/v1/watch-plans/preview", response_model=WatchPlanPreviewResponse)
def preview_watch_plan(
    req: WatchPlanPreviewRequest,
    current_user: User | None = Depends(get_optional_user),
):
    """Translate natural language instruction into a validated WatchPlan preview without persisting."""
    try:
        planner = NaturalLanguageWatchPlanner()
        return planner.preview_plan(
            message=req.message,
            url=req.url,
            timezone=req.timezone,
        )
    except Exception as exc:
        logger.exception("Failed to preview watch plan: %s", exc)
        return WatchPlanPreviewResponse(
            status="needs_clarification",
            missing=["instruction"],
            clarification_prompt="Could not parse monitoring instruction. Please specify a valid Daraz product URL and condition.",
            message=str(exc),
        )


@app.post("/v1/watches/from-plan", response_model=WatchRead, status_code=status.HTTP_201_CREATED)
def create_watch_from_plan(
    req: WatchCreateFromPlanRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Create a persistent Watch from a validated WatchPlan scoped to current user."""
    planner = NaturalLanguageWatchPlanner()
    target_user_id = current_user.id if current_user is not None else req.user_id
    if not target_user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        watch = planner.create_watch_from_plan(
            db=db,
            user_id=target_user_id,
            plan=req.plan,
        )
        logger.info("Watch created from AI plan: %s ('%s') for user %s", watch.id, watch.title, target_user_id)
        return watch
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Failed to create watch from plan: %s", exc)
        raise HTTPException(status_code=500, detail=f"Failed to create watch: {exc}") from exc

