UPDATE watch_runs
SET status = 'pending'
WHERE status = 'queued';

ALTER TABLE watch_runs
    ALTER COLUMN status SET DEFAULT 'pending';

ALTER TABLE watch_runs
    ADD CONSTRAINT ck_watch_runs_status
    CHECK (status IN ('pending', 'running', 'succeeded', 'failed'));

CREATE UNIQUE INDEX uq_active_watch_runs_per_watch
    ON watch_runs (watch_id)
    WHERE status IN ('pending', 'running');

ALTER TABLE snapshots
    ADD COLUMN watch_id UUID;

UPDATE snapshots AS snapshot
SET watch_id = run.watch_id
FROM watch_runs AS run
WHERE snapshot.run_id = run.id;

ALTER TABLE snapshots
    ALTER COLUMN watch_id SET NOT NULL,
    ADD CONSTRAINT fk_snapshots_watch_id
        FOREIGN KEY (watch_id) REFERENCES watches(id) ON DELETE CASCADE;

ALTER TABLE snapshots
    ADD COLUMN captured_at TIMESTAMPTZ;

UPDATE snapshots
SET captured_at = extracted_at;

ALTER TABLE snapshots
    ALTER COLUMN captured_at SET NOT NULL,
    ALTER COLUMN captured_at SET DEFAULT now(),
    ADD COLUMN metadata JSONB NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX idx_snapshots_watch_id ON snapshots(watch_id);
