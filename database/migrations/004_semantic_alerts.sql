-- Migration 004: Semantic Alerts and Watch Events

ALTER TABLE alerts
    ADD COLUMN IF NOT EXISTS run_id UUID REFERENCES watch_runs(id) ON DELETE CASCADE,
    ADD COLUMN IF NOT EXISTS event_type VARCHAR(64) NOT NULL DEFAULT 'alert',
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(128);

CREATE INDEX IF NOT EXISTS idx_alerts_run_id ON alerts(run_id);
CREATE INDEX IF NOT EXISTS idx_alerts_event_type ON alerts(event_type);
CREATE UNIQUE INDEX IF NOT EXISTS uq_alerts_idempotency
    ON alerts(watch_id, idempotency_key)
    WHERE idempotency_key IS NOT NULL;
