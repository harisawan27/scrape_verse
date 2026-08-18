import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# Native UUID in PostgreSQL, portable UUID-compatible storage in SQLite tests.
UUID_TYPE = Uuid(as_uuid=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)

    watches: Mapped[list["Watch"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Watch(Base):
    __tablename__ = "watches"

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    monitoring_spec: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    user: Mapped[User] = relationship(back_populates="watches")
    schedule: Mapped["Schedule"] = relationship(back_populates="watch", cascade="all, delete-orphan", uselist=False)
    runs: Mapped[list["WatchRun"]] = relationship(back_populates="watch", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="watch", cascade="all, delete-orphan")
    repairs: Mapped[list["ScraperRepair"]] = relationship(back_populates="watch", cascade="all, delete-orphan")




class Schedule(Base):
    __tablename__ = "schedules"

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, unique=True)
    cadence: Mapped[str] = mapped_column(String(40), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    next_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now, nullable=False)

    watch: Mapped[Watch] = relationship(back_populates="schedule")


class WatchRun(Base):
    __tablename__ = "watch_runs"
    __table_args__ = (
        UniqueConstraint("watch_id", "scheduled_for", name="uq_watch_runs_scheduled_for"),
        CheckConstraint("status IN ('pending', 'running', 'succeeded', 'failed')", name="ck_watch_runs_status"),
        Index(
            "uq_active_watch_runs_per_watch",
            "watch_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'running')"),
            sqlite_where=text("status IN ('pending', 'running')"),
        ),
    )

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    bright_data_collection_id: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    error_detail: Mapped[str | None] = mapped_column(Text)

    watch: Mapped[Watch] = relationship(back_populates="runs")
    snapshot: Mapped["Snapshot | None"] = relationship(back_populates="run", cascade="all, delete-orphan", uselist=False)
    changes: Mapped[list["Change"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    repair: Mapped["ScraperRepair | None"] = relationship(back_populates="run", cascade="all, delete-orphan", uselist=False)


class Snapshot(Base):
    __tablename__ = "snapshots"
    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watch_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=False, default=dict)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    run: Mapped[WatchRun] = relationship(back_populates="snapshot")


class Change(Base):
    __tablename__ = "changes"
    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watch_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    change_type: Mapped[str] = mapped_column(String(64), nullable=False)
    details: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    run: Mapped[WatchRun] = relationship(back_populates="changes")


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        Index(
            "uq_alerts_idempotency",
            "watch_id",
            "idempotency_key",
            unique=True,
            postgresql_where=text("idempotency_key IS NOT NULL"),
            sqlite_where=text("idempotency_key IS NOT NULL"),
        ),
    )

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str | None] = mapped_column(UUID_TYPE, ForeignKey("watch_runs.id", ondelete="CASCADE"), nullable=True, index=True)
    change_id: Mapped[str | None] = mapped_column(UUID_TYPE, ForeignKey("changes.id", ondelete="SET NULL"), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, default="alert", index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    details: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    condition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)

    watch: Mapped[Watch] = relationship(back_populates="alerts")
    run: Mapped[WatchRun | None] = relationship(back_populates="alerts")


class ScraperRepair(Base):
    __tablename__ = "scraper_repairs"
    __table_args__ = (
        Index(
            "uq_scraper_repairs_run_active",
            "run_id",
            unique=True,
            postgresql_where=text("status IN ('pending', 'in_progress', 'pending_answer', 'requires_manual_promotion')"),
            sqlite_where=text("status IN ('pending', 'in_progress', 'pending_answer', 'requires_manual_promotion')"),
        ),
    )

    id: Mapped[str] = mapped_column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    watch_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watches.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(UUID_TYPE, ForeignKey("watch_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    collector_id: Mapped[str] = mapped_column(String(128), nullable=False)
    refactor_job_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    repair_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    missing_fields: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="pending", index=True)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

    watch: Mapped[Watch] = relationship(back_populates="repairs")
    run: Mapped[WatchRun] = relationship(back_populates="repair")


