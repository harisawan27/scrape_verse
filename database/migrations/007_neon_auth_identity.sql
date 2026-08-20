-- 007_neon_auth_identity.sql
-- Integrates public.users with managed neon_auth schema
-- Auth_id maps to neon_auth.user.id. password_hash is deprecated.

CREATE INDEX IF NOT EXISTS idx_users_auth_id ON public.users (auth_id);

-- Ensure password_hash is nullable (deprecated from application code)
ALTER TABLE public.users ALTER COLUMN password_hash DROP NOT NULL;
