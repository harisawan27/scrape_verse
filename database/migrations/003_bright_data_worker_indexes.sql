-- Migration 003: Index for asynchronous worker recovery of running Bright Data jobs

CREATE INDEX IF NOT EXISTS idx_watch_runs_running_bright_data
    ON watch_runs (status)
    WHERE bright_data_collection_id IS NOT NULL AND status = 'running';
