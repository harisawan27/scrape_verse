CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(320) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    title VARCHAR(255) NOT NULL,
    instruction TEXT NOT NULL,
    monitoring_spec JSONB NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'paused', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID NOT NULL UNIQUE REFERENCES watches(id) ON DELETE CASCADE,
    cadence VARCHAR(40) NOT NULL CHECK (cadence IN ('hourly', 'daily', 'weekly', 'custom')),
    timezone VARCHAR(64) NOT NULL,
    next_due_at TIMESTAMPTZ NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE watch_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    scheduled_for TIMESTAMPTZ NOT NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'queued',
    bright_data_collection_id VARCHAR(128) UNIQUE,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    error_code VARCHAR(100),
    error_detail TEXT,
    CONSTRAINT uq_watch_runs_scheduled_for UNIQUE (watch_id, scheduled_for)
);

CREATE TABLE snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL UNIQUE REFERENCES watch_runs(id) ON DELETE CASCADE,
    payload JSONB NOT NULL,
    extracted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES watch_runs(id) ON DELETE CASCADE,
    change_type VARCHAR(64) NOT NULL,
    details JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    change_id UUID REFERENCES changes(id) ON DELETE SET NULL,
    status VARCHAR(30) NOT NULL DEFAULT 'open',
    condition_snapshot JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_watches_user_id ON watches(user_id);
CREATE INDEX idx_watches_status ON watches(status);
CREATE INDEX idx_schedules_next_due_at ON schedules(next_due_at) WHERE enabled;
CREATE INDEX idx_watch_runs_watch_id ON watch_runs(watch_id);
CREATE INDEX idx_changes_watch_id ON changes(watch_id);
CREATE INDEX idx_alerts_watch_id ON alerts(watch_id);

