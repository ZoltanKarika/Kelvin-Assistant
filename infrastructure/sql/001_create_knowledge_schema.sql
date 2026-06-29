-- Kelvin Assistant v0.4 Knowledge schema.
--
-- This first migration is intentionally plain SQL so the database structure is
-- easy to read while learning. A later milestone may wrap these changes in
-- Alembic once the schema direction is stable.

BEGIN;

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS knowledge_collections (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL UNIQUE,
    description text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_collections_name_not_blank
        CHECK (length(trim(name)) > 0)
);

CREATE TABLE IF NOT EXISTS knowledge_documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    collection_id uuid NOT NULL REFERENCES knowledge_collections(id) ON DELETE CASCADE,
    source_uri text NOT NULL,
    title text,
    content_hash text NOT NULL,
    mime_type text NOT NULL,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_documents_source_uri_not_blank
        CHECK (length(trim(source_uri)) > 0),
    CONSTRAINT knowledge_documents_content_hash_not_blank
        CHECK (length(trim(content_hash)) > 0),
    CONSTRAINT knowledge_documents_mime_type_not_blank
        CHECK (length(trim(mime_type)) > 0),
    CONSTRAINT knowledge_documents_metadata_is_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_knowledge_documents_collection_source
    ON knowledge_documents (collection_id, source_uri);

CREATE UNIQUE INDEX IF NOT EXISTS ux_knowledge_documents_collection_hash
    ON knowledge_documents (collection_id, content_hash);

CREATE TABLE IF NOT EXISTS knowledge_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id uuid NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    token_count integer,
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_chunks_chunk_index_non_negative
        CHECK (chunk_index >= 0),
    CONSTRAINT knowledge_chunks_content_not_blank
        CHECK (length(trim(content)) > 0),
    CONSTRAINT knowledge_chunks_token_count_positive
        CHECK (token_count IS NULL OR token_count > 0),
    CONSTRAINT knowledge_chunks_metadata_is_object
        CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_knowledge_chunks_document_index
    ON knowledge_chunks (document_id, chunk_index);

CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_document_id
    ON knowledge_chunks (document_id);

CREATE TABLE IF NOT EXISTS knowledge_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id uuid NOT NULL REFERENCES knowledge_chunks(id) ON DELETE CASCADE,
    embedding_model text NOT NULL,
    embedding_dimension integer NOT NULL,
    embedding vector(768) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT knowledge_embeddings_model_not_blank
        CHECK (length(trim(embedding_model)) > 0),
    CONSTRAINT knowledge_embeddings_dimension_matches_vector
        CHECK (embedding_dimension = 768)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_knowledge_embeddings_chunk_model
    ON knowledge_embeddings (chunk_id, embedding_model);

CREATE INDEX IF NOT EXISTS ix_knowledge_embeddings_vector_cosine
    ON knowledge_embeddings
    USING hnsw (embedding vector_cosine_ops);

COMMIT;
