-- Migration 004: Phase 1 Hybrid Search, Full-Text Search Vector, and Multi-Tenancy
-- Adds tsvector columns, GIN indexes for lexical BM25 search, and tenant_id isolation.

-- 1. Add tenant_id to core tables
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';

ALTER TABLE candidate_matches
    ADD COLUMN IF NOT EXISTS tenant_id VARCHAR(64) NOT NULL DEFAULT 'default';

CREATE INDEX IF NOT EXISTS idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX IF NOT EXISTS idx_candidates_tenant ON candidates(tenant_id);

-- 2. Add search_vector (tsvector) for sparse lexical search
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;

ALTER TABLE candidates
    ADD COLUMN IF NOT EXISTS search_vector TSVECTOR;

CREATE INDEX IF NOT EXISTS idx_jobs_search_vector ON jobs USING GIN (search_vector);
CREATE INDEX IF NOT EXISTS idx_candidates_search_vector ON candidates USING GIN (search_vector);

-- 3. Automatic trigger functions to compute tsvector for jobs and candidates
CREATE OR REPLACE FUNCTION update_job_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.title, '')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.description, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_jobs_search_vector ON jobs;
CREATE TRIGGER trg_jobs_search_vector
BEFORE INSERT OR UPDATE ON jobs
FOR EACH ROW EXECUTE FUNCTION update_job_search_vector();


CREATE OR REPLACE FUNCTION update_candidate_search_vector() RETURNS trigger AS $$
BEGIN
    NEW.search_vector :=
        setweight(to_tsvector('english', COALESCE(NEW.name, '')), 'A') ||
        setweight(to_tsvector('english', array_to_string(COALESCE(NEW.skills, '{}'), ' ')), 'A') ||
        setweight(to_tsvector('english', COALESCE(NEW.parsed_resume::text, '')), 'B');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_candidates_search_vector ON candidates;
CREATE TRIGGER trg_candidates_search_vector
BEFORE INSERT OR UPDATE ON candidates
FOR EACH ROW EXECUTE FUNCTION update_candidate_search_vector();

-- Populate initial search_vectors for existing rows
UPDATE jobs SET title = title WHERE search_vector IS NULL;
UPDATE candidates SET name = name WHERE search_vector IS NULL;
