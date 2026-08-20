-- Migration 006: Add user authentication credentials and external auth identity mapping

ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash TEXT NULL;
ALTER TABLE users ADD COLUMN IF NOT EXISTS auth_id TEXT NULL;

CREATE INDEX IF NOT EXISTS ix_users_auth_id ON users (auth_id);
