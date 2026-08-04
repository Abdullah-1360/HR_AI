-- Migration 003: Fix embedding column dimension to VECTOR(1024)
-- Cohere embed-english-v3.0 outputs 1024-dimensional vectors.
-- Jobs and candidates tables are empty at this point so we can
-- safely drop and recreate the columns.

ALTER TABLE jobs
    DROP COLUMN IF EXISTS embedding;

ALTER TABLE jobs
    ADD COLUMN embedding VECTOR(1024);

ALTER TABLE candidates
    DROP COLUMN IF EXISTS embedding;

ALTER TABLE candidates
    ADD COLUMN embedding VECTOR(1024);

-- Recreate HNSW indexes on correct dimension
DROP INDEX IF EXISTS idx_jobs_embedding;
DROP INDEX IF EXISTS idx_candidates_embedding;

CREATE INDEX IF NOT EXISTS idx_jobs_embedding
    ON jobs USING hnsw (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_candidates_embedding
    ON candidates USING hnsw (embedding vector_cosine_ops);
