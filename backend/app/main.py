from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import check_database_connection, get_db
from app.repositories import WatchRepository
from app.schemas import (
    AlertRead,
    ChangeRead,
    ScraperRepairRead,
    UserCreate,
    UserRead,
    WatchCreate,
    WatchCreateFromPlanRequest,
    WatchPlanPreviewRequest,
    WatchPlanPreviewResponse,
    WatchRead,
    WatchRunRead,
    WatchUpdate,
)
from app.services.planner import NaturalLanguageWatchPlanner



from app.services.runs import (
    ActiveRunExistsError,
    MockRunExecutor,
    RunCreationService,
    WatchNotEligibleError,
    WatchNotFoundError,
)

app = FastAPI(title="Web Radar API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check; it intentionally does not establish a database connection."""
    return {"status": "ok"}


@app.get("/health/database")
def database_health() -> dict[str, str]:
    """Readiness check for Neon/PostgreSQL; it returns no connection details."""
    try:
        check_database_connection()
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ok", "database": "available"}


@app.post("/v1/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(data: UserCreate, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    try:
        return repository.create_user(data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="email already exists") from exc


@app.post("/v1/watches", response_model=WatchRead, status_code=status.HTTP_201_CREATED)
def create_watch(data: WatchCreate, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    if repository.get_user(data.user_id) is None:
        raise HTTPException(status_code=404, detail="user not found")
    return repository.create(data)


@app.get("/v1/watches", response_model=list[WatchRead])
def list_watches(user_id: str, db: Session = Depends(get_db)):
    return WatchRepository(db).list_for_user(user_id)


@app.get("/v1/watches/{watch_id}", response_model=WatchRead)
def get_watch(watch_id: str, db: Session = Depends(get_db)):
    watch = WatchRepository(db).get(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return watch


@app.patch("/v1/watches/{watch_id}", response_model=WatchRead)
def update_watch(watch_id: str, data: WatchUpdate, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    watch = repository.get(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.update(watch, data)


@app.delete("/v1/watches/{watch_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_watch(watch_id: str, db: Session = Depends(get_db)) -> Response:
    repository = WatchRepository(db)
    watch = repository.get(watch_id)
    if watch is None:
        raise HTTPException(status_code=404, detail="watch not found")
    repository.delete(watch)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post("/v1/watches/{watch_id}/runs", response_model=WatchRunRead, status_code=status.HTTP_201_CREATED)
def trigger_watch_run(watch_id: str, execute_now: bool = True, db: Session = Depends(get_db)):
    """Create a durable pending Run, then optionally execute it via MockRunExecutor."""
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

    repository = WatchRepository(db)
    return repository.get_run(run.id)


@app.get("/v1/watches/{watch_id}/runs", response_model=list[WatchRunRead])
def list_watch_runs(watch_id: str, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    if repository.get(watch_id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_runs_for_watch(watch_id)


@app.get("/v1/runs/{run_id}", response_model=WatchRunRead)
def get_run(run_id: str, db: Session = Depends(get_db)):
    run = WatchRepository(db).get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@app.get("/v1/watches/{watch_id}/changes", response_model=list[ChangeRead])
def list_watch_changes(watch_id: str, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    if repository.get(watch_id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_changes_for_watch(watch_id)


@app.get("/v1/watches/{watch_id}/events", response_model=list[AlertRead])
@app.get("/v1/watches/{watch_id}/alerts", response_model=list[AlertRead])
def list_watch_events(watch_id: str, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    if repository.get(watch_id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_alerts_for_watch(watch_id)


@app.get("/v1/watches/{watch_id}/repairs", response_model=list[ScraperRepairRead])
def list_watch_repairs(watch_id: str, db: Session = Depends(get_db)):
    repository = WatchRepository(db)
    if repository.get(watch_id) is None:
        raise HTTPException(status_code=404, detail="watch not found")
    return repository.list_repairs_for_watch(watch_id)




@app.post("/v1/scheduler/tick", response_model=list[WatchRunRead])
def run_scheduler_tick(db: Session = Depends(get_db)):
    """Development trigger: Discovers and executes all currently due Watches."""
    from app.services.scheduler import SchedulerService

    scheduler = SchedulerService(db)
    runs = scheduler.tick()
    repository = WatchRepository(db)
    return [repository.get_run(r.id) for r in runs if repository.get_run(r.id) is not None]


@app.get("/v1/scheduler/status")
def get_scheduler_status():
    from app.config import get_settings

    settings = get_settings()
    return {
        "status": "ready",
        "poll_interval_seconds": settings.scheduler_poll_interval_seconds,
        "scheduler_enabled": settings.scheduler_enabled,
    }


@app.post("/v1/watch-plans/preview", response_model=WatchPlanPreviewResponse)
def preview_watch_plan(req: WatchPlanPreviewRequest):
    """Translate natural language instruction into a validated WatchPlan preview without persisting."""
    planner = NaturalLanguageWatchPlanner()
    return planner.preview_plan(
        message=req.message,
        url=req.url,
        timezone=req.timezone,
    )


@app.post("/v1/watches/from-plan", response_model=WatchRead, status_code=status.HTTP_201_CREATED)
def create_watch_from_plan(req: WatchCreateFromPlanRequest, db: Session = Depends(get_db)):
    """Create a persistent Watch from a validated WatchPlan."""
    planner = NaturalLanguageWatchPlanner()
    try:
        watch = planner.create_watch_from_plan(
            db=db,
            user_id=req.user_id,
            plan=req.plan,
        )
        return watch
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc



