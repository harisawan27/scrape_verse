from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import Alert, Change, ScraperRepair, Schedule, Snapshot, User, Watch, WatchRun
from app.schemas import UserCreate, WatchCreate, WatchUpdate


class WatchRepository:
    def __init__(self, db: Session):
        self.db = db

    def create_user(self, data: UserCreate) -> User:
        user = User(email=data.email)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def get_user(self, user_id: str) -> User | None:
        return self.db.get(User, user_id)

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

    def get(self, watch_id: str) -> Watch | None:
        statement = select(Watch).options(joinedload(Watch.schedule)).where(Watch.id == watch_id)
        return self.db.scalar(statement)

    def list_for_user(self, user_id: str) -> list[Watch]:
        statement = (
            select(Watch)
            .options(joinedload(Watch.schedule))
            .where(Watch.user_id == user_id)
            .order_by(Watch.created_at.desc())
        )
        return list(self.db.scalars(statement).unique())

    def update(self, watch: Watch, data: WatchUpdate) -> Watch:
        values = data.model_dump(exclude_unset=True, exclude={"schedule"})
        if "url" in values:
            values["url"] = str(values["url"])
        for field, value in values.items():
            setattr(watch, field, value)
        if data.schedule is not None:
            for field, value in data.schedule.model_dump().items():
                setattr(watch.schedule, field, value)
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




