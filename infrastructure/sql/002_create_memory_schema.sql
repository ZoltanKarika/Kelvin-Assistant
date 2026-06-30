-- Kelvin Assistant v0.5 Memory schema.
--
-- Memory is intentionally separated from the v0.4 knowledge/RAG tables because
-- memories have different origin, retention, deletion, and trust rules.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS memory_items (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    scope text NOT NULL,
    kind text NOT NULL,
    content text NOT NULL,
    source text NOT NULL,
    confidence numeric(4, 3) NOT NULL DEFAULT 1.000,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz,
    deleted_at timestamptz,
    CONSTRAINT memory_items_scope_allowed
        CHECK (scope IN ('user', 'project', 'session', 'system')),
    CONSTRAINT memory_items_kind_allowed
        CHECK (kind IN ('preference', 'fact', 'summary', 'task_state')),
    CONSTRAINT memory_items_content_not_blank
        CHECK (length(trim(content)) > 0),
    CONSTRAINT memory_items_source_not_blank
        CHECK (length(trim(source)) > 0),
    CONSTRAINT memory_items_confidence_range
        CHECK (confidence >= 0 AND confidence <= 1),
    CONSTRAINT memory_items_metadata_is_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX IF NOT EXISTS ix_memory_items_active_scope_kind
    ON memory_items (scope, kind)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_memory_items_expires_at
    ON memory_items (expires_at)
    WHERE expires_at IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_memory_items_created_at
    ON memory_items (created_at);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id uuid NOT NULL REFERENCES memory_items(id) ON DELETE CASCADE,
    embedding_model text NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding vector(768) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT memory_embeddings_model_not_blank
        CHECK (length(trim(embedding_model)) > 0),
    CONSTRAINT memory_embeddings_dimension_matches_vector
        CHECK (embedding_dimension = 768)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_memory_embeddings_memory_model
    ON memory_embeddings (memory_id, embedding_model);

CREATE INDEX IF NOT EXISTS ix_memory_embeddings_vector_cosine
    ON memory_embeddings
    USING hnsw (embedding vector_cosine_ops);

COMMIT;
