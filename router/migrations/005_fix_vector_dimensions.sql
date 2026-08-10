-- Migration 005: Fix embedding vector dimensions from 1536 to 1024
-- The codebase uses Cohere embed-english-v3.0 which outputs 1024-dim vectors,
-- but the original migration created columns as VECTOR(1536).

ALTER TABLE jobs ALTER COLUMN embedding TYPE VECTOR(1024);
ALTER TABLE candidates ALTER COLUMN embedding TYPE VECTOR(1024);
