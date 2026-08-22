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
from app.models import User, utc_now
from app.repositories import WatchRepository
from app.schemas import (
    ActivityEventRead,
    AlertRead,
    ChangeRead,
    ConversationMessageRead,
    ConversationRead,
    ConversationSummaryRead,
    ConversationalPromptRequest,
    ConversationalResponseRead,
    ScraperRepairRead,
    UserCreate,
    UserRead,
    WatchChatRequest,
    WatchChatResponse,
    WatchCreate,
    WatchCreateFromPlanRequest,
    WatchOverviewRead,
    WatchPlanPreviewRequest,
    WatchPlanPreviewResponse,
    WatchRead,
    WatchRunRead,
    WatchSummaryRead,
    WatchTargetCreate,
    WatchTargetRead,
    WatchUpdate,
)
from app.services.conversational_planner import ConversationalDiscoveryEngine, ConversationalIntent
from app.services.planner import NaturalLanguageWatchPlanner
from app.services.watch_actions import WatchActionHandler
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
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    if target_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return repository.list_summaries_for_user(target_user.id)


@app.get("/v1/watches/{watch_id}", response_model=WatchRead)
def get_watch(
    watch_id: str,
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    watch = repository.get(watch_id, user_id=uid)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return watch


@app.get("/v1/watches/{watch_id}/overview", response_model=WatchOverviewRead)
def get_watch_overview(
    watch_id: str,
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    overview = repository.get_watch_overview(watch_id, user_id=uid)
    if overview is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return overview


@app.get("/v1/activity", response_model=list[ActivityEventRead])
def list_activity(
    user_id: str | None = None,
    limit: int = 50,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    if target_user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return repository.list_activity_for_user(target_user.id, limit=limit)


@app.patch("/v1/watches/{watch_id}", response_model=WatchRead)
def update_watch(
    watch_id: str,
    data: WatchUpdate,
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    watch = repository.get(watch_id, user_id=uid)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    updated = repository.update(watch, data)
    logger.info("Watch updated: %s (status=%s)", watch.id, updated.status)
    return updated


@app.delete("/v1/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(
    watch_id: str,
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
) -> Response:
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    watch = repository.get(watch_id, user_id=uid)
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
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    watch = repository.get(watch_id, user_id=uid)
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
    user_id: str | None = None,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    repository = WatchRepository(db)
    target_user = current_user
    if target_user is None and user_id:
        target_user = repository.get_user(user_id)
    uid = target_user.id if target_user else None
    if repository.get(watch_id, user_id=uid) is None:
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


# ==============================================================================
# Phase 8: Conversational Web Radar (Ask, Discover, Watch)
# ==============================================================================

@app.post("/v1/conversations", response_model=ConversationalResponseRead)
@app.post("/api/conversations", response_model=ConversationalResponseRead)
def process_conversational_prompt(
    req: ConversationalPromptRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Main Conversational Web Radar entry point.
    Classifies mode (ASK, WATCH, ASK_AND_WATCH, CLARIFICATION),
    performs Google Search discovery & URL context grounding,
    cites official sources, and creates persistent Watches when requested.
    """
    repo = WatchRepository(db)

    # 1. Resolve user
    user_id = current_user.id if current_user else None
    if not user_id:
        # Fallback to demo user for testing/unauthenticated exploration
        user = repo.get_first_user()
        if not user:
            user = repo.create_user("demo@webradar.local")
        user_id = user.id

    # 2. Resolve or create Conversation
    conversation = None
    if req.conversation_id:
        conversation = repo.get_conversation(req.conversation_id, user_id=user_id)

    if not conversation:
        title = req.message[:40] + ("..." if len(req.message) > 40 else "")
        conversation = repo.create_conversation(user_id=user_id, title=title)

    # 3. Store user message in conversation
    repo.add_conversation_message(
        conversation_id=conversation.id,
        role="user",
        content=req.message,
        message_type="user",
    )

    # 4. Run Conversational Discovery & Intelligence Engine
    engine = ConversationalDiscoveryEngine(
        gemini_api_key=settings.gemini_api_key,
        model_name=settings.gemini_model_name,
        base_url=settings.gemini_base_url,
    )
    plan_result = engine.plan_conversation(
        message=req.message,
        url=req.url,
        selected_option=req.selected_option,
    )

    created_watch: WatchRead | None = None

    # 5. Execute Watch creation if mode is WATCH or ASK_AND_WATCH
    if plan_result.mode in (ConversationalIntent.WATCH, ConversationalIntent.ASK_AND_WATCH) and plan_result.watch_url:
        try:
            from app.models import Watch, Schedule
            from app.services.scheduler import calculate_next_due_at
            import uuid

            watch_obj = Watch(
                id=str(uuid.uuid4()),
                user_id=user_id,
                url=plan_result.watch_url,
                title=plan_result.watch_title or "Discovered Watch Target",
                instruction=plan_result.watch_intent or req.message,
                monitoring_spec={
                    "rules": plan_result.rules,
                    "field": plan_result.rules[0].get("field", "price") if plan_result.rules else "price",
                    "currency": plan_result.rules[0].get("currency", "PKR") if plan_result.rules else "PKR",
                    "threshold": plan_result.rules[0].get("value") if plan_result.rules else None,
                    "cadence": plan_result.cadence_name,
                    "collector_id": settings.bright_data_collector_id,
                },
                status="active",
            )
            db.add(watch_obj)

            # Add Schedule
            sched_obj = Schedule(
                watch_id=watch_obj.id,
                cadence=plan_result.cadence_name,
                timezone="Asia/Karachi",
                next_due_at=calculate_next_due_at(
                    utc_now(),
                    plan_result.cadence_name,
                    tz_name="Asia/Karachi",
                    custom_minutes=plan_result.cadence_minutes,
                ),
                enabled=True,
            )
            db.add(sched_obj)

            # Add WatchTargets (multi-target support)
            for t in plan_result.targets:
                repo.add_watch_target(
                    watch_id=watch_obj.id,
                    url=t.get("url", plan_result.watch_url),
                    target_type=t.get("target_type", "primary"),
                    source_confidence=float(t.get("source_confidence", 1.0)),
                )

            db.commit()
            db.refresh(watch_obj)
            created_watch = WatchRead.model_validate(watch_obj)

            # Trigger immediate baseline scan
            try:
                from app.services.runs import RunCreationService, BrightDataRunExecutor, MockRunExecutor
                run_creator = RunCreationService(db)
                run = run_creator.create(watch_id=watch_obj.id)
                executor = BrightDataRunExecutor(db) if settings.bright_data_api_key else MockRunExecutor(db)
                executor.execute(run)
            except Exception as e:
                logger.warning("Could not execute immediate baseline run for new watch: %s", e)

        except Exception as exc:
            logger.exception("Failed to persist watch during conversational discovery: %s", exc)

    # 6. Record Assistant Message in DB
    msg_type = "answer"
    if plan_result.mode == ConversationalIntent.WATCH:
        msg_type = "watch_created"
    elif plan_result.mode == ConversationalIntent.CLARIFICATION:
        msg_type = "clarification"
    elif plan_result.mode == ConversationalIntent.ASK_AND_WATCH:
        msg_type = "scan_result"

    sources_dict = [s.model_dump() for s in plan_result.sources]
    meta = {
        "mode": plan_result.mode,
        "sources": sources_dict,
        "watch_id": created_watch.id if created_watch else None,
        "watch_title": created_watch.title if created_watch else None,
        "clarification_options": plan_result.clarification_options,
    }
    meta.update(plan_result.metadata)

    asst_msg = repo.add_conversation_message(
        conversation_id=conversation.id,
        role="assistant",
        content=plan_result.content,
        message_type=msg_type,
        metadata=meta,
    )

    return ConversationalResponseRead(
        conversation_id=conversation.id,
        message_id=asst_msg.id,
        role="assistant",
        mode=plan_result.mode,
        content=plan_result.content,
        message_type=msg_type,
        sources=plan_result.sources,
        watch=created_watch,
        clarification_options=plan_result.clarification_options,
        metadata_=meta,
    )


@app.get("/v1/conversations", response_model=list[ConversationSummaryRead])
@app.get("/api/conversations", response_model=list[ConversationSummaryRead])
def list_conversations(
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """List recent conversations for user."""
    repo = WatchRepository(db)
    user_id = current_user.id if current_user else None
    if not user_id:
        user = repo.get_first_user()
        user_id = user.id if user else None
    if not user_id:
        return []

    convs = repo.list_conversations_for_user(user_id=user_id)
    summaries = []
    for c in convs:
        last_msg = c.messages[-1].content if c.messages else None
        summaries.append(
            ConversationSummaryRead(
                id=c.id,
                user_id=c.user_id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=len(c.messages),
                latest_message_preview=last_msg[:60] if last_msg else None,
            )
        )
    return summaries


@app.get("/v1/conversations/{id}", response_model=ConversationRead)
@app.get("/api/conversations/{id}", response_model=ConversationRead)
def get_conversation(
    id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get complete message history for a conversation."""
    repo = WatchRepository(db)
    user_id = current_user.id if current_user else None
    conv = repo.get_conversation(id, user_id=user_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    messages_read = [
        ConversationMessageRead(
            id=m.id,
            conversation_id=m.conversation_id,
            role=m.role,
            content=m.content,
            message_type=m.message_type,
            metadata=m.metadata_ or {},
            created_at=m.created_at,
        )
        for m in conv.messages
    ]
    return ConversationRead(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_read,
    )


@app.delete("/v1/conversations/{id}", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/api/conversations/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    id: str,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Delete a conversation."""
    repo = WatchRepository(db)
    user_id = current_user.id if current_user else None
    if not user_id:
        user = repo.get_first_user()
        user_id = user.id if user else None
    if not user_id or not repo.delete_conversation(id, user_id=user_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/watches/{id}/chat", response_model=WatchChatResponse)
@app.post("/api/watches/{id}/chat", response_model=WatchChatResponse)
def watch_detail_chat(
    id: str,
    req: WatchChatRequest,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Contextual conversational agent for individual Watch pages with function-calling action execution."""
    repo = WatchRepository(db)
    user_id = current_user.id if current_user else None
    if not user_id:
        user = repo.get_first_user()
        user_id = user.id if user else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")

    handler = WatchActionHandler(db, user_id=user_id)
    return handler.handle_message(watch_id=id, message=req.message)


@app.get("/v1/watches/{id}/targets", response_model=list[WatchTargetRead])
@app.get("/api/watches/{id}/targets", response_model=list[WatchTargetRead])
def list_watch_targets(
    id: str,
    db: Session = Depends(get_db),
):
    """List all monitored target URLs for a watch."""
    repo = WatchRepository(db)
    targets = repo.list_targets_for_watch(watch_id=id)
    return [
        WatchTargetRead(
            id=t.id,
            watch_id=t.watch_id,
            url=t.url,
            target_type=t.target_type,
            source_confidence=t.source_confidence,
            enabled=t.enabled,
            created_at=t.created_at,
        )
        for t in targets
    ]


@app.post("/v1/watches/{id}/targets", response_model=WatchTargetRead, status_code=status.HTTP_201_CREATED)
@app.post("/api/watches/{id}/targets", response_model=WatchTargetRead, status_code=status.HTTP_201_CREATED)
def add_watch_target(
    id: str,
    req: WatchTargetCreate,
    current_user: User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Add a target URL to a watch."""
    repo = WatchRepository(db)
    user_id = current_user.id if current_user else None
    if user_id:
        watch = repo.get_user_watch(user_id, id)
        if not watch:
            raise HTTPException(status_code=404, detail="Watch not found")

    target = repo.add_watch_target(
        watch_id=id,
        url=req.url,
        target_type=req.target_type,
        source_confidence=req.source_confidence,
    )
    return WatchTargetRead(
        id=target.id,
        watch_id=target.watch_id,
        url=target.url,
        target_type=target.target_type,
        source_confidence=target.source_confidence,
        enabled=target.enabled,
        created_at=target.created_at,
    )


@app.delete("/v1/watches/{id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
@app.delete("/api/watches/{id}/targets/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch_target(
    id: str,
    target_id: str,
    db: Session = Depends(get_db),
):
    """Remove a target URL from a watch."""
    repo = WatchRepository(db)
    if not repo.remove_watch_target(watch_id=id, target_id=target_id):
        raise HTTPException(status_code=404, detail="Target not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


