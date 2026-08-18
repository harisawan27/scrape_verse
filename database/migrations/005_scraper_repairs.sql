-- Migration 005: Scraper Studio Self-Healing and Repairs

CREATE TABLE IF NOT EXISTS scraper_repairs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    watch_id UUID NOT NULL REFERENCES watches(id) ON DELETE CASCADE,
    run_id UUID NOT NULL REFERENCES watch_runs(id) ON DELETE CASCADE,
    collector_id VARCHAR(128) NOT NULL,
    refactor_job_id VARCHAR(128),
    repair_prompt TEXT NOT NULL,
    missing_fields JSONB NOT NULL DEFAULT '[]'::jsonb,
    status VARCHAR(40) NOT NULL DEFAULT 'pending',
    failure_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_scraper_repairs_watch_id ON scraper_repairs(watch_id);
CREATE INDEX IF NOT EXISTS idx_scraper_repairs_run_id ON scraper_repairs(run_id);
CREATE INDEX IF NOT EXISTS idx_scraper_repairs_status ON scraper_repairs(status);
CREATE UNIQUE INDEX IF NOT EXISTS uq_scraper_repairs_run_active
    ON scraper_repairs(run_id)
    WHERE status IN ('pending', 'in_progress', 'pending_answer', 'requires_manual_promotion');
