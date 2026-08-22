-- 008_conversations_and_targets.sql
-- Adds persistent conversations, conversation messages, and multiple watch targets per watch.

CREATE TABLE IF NOT EXISTS public.conversations (
    id UUID PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL DEFAULT 'New Task',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON public.conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON public.conversations (updated_at DESC);

CREATE TABLE IF NOT EXISTS public.conversation_messages (
    id UUID PRIMARY KEY,
    conversation_id UUID NOT NULL REFERENCES public.conversations(id) ON DELETE CASCADE,
    role VARCHAR(32) NOT NULL DEFAULT 'user',
    content TEXT NOT NULL,
    message_type VARCHAR(64) NOT NULL DEFAULT 'user',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON public.conversation_messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON public.conversation_messages (created_at ASC);

CREATE TABLE IF NOT EXISTS public.watch_targets (
    id UUID PRIMARY KEY,
    watch_id UUID NOT NULL REFERENCES public.watches(id) ON DELETE CASCADE,
    url TEXT NOT NULL,
    target_type VARCHAR(64) NOT NULL DEFAULT 'primary',
    source_confidence DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_watch_targets_watch_id ON public.watch_targets (watch_id);
