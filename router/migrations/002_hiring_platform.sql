-- AI Hiring Platform Schema Extension
-- Enables vector search (pgvector) and creates jobs, candidates, and matches tables.

CREATE EXTENSION IF NOT EXISTS vector;

-- Job postings / descriptions
CREATE TABLE IF NOT EXISTS jobs (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title               TEXT NOT NULL,
    description         TEXT NOT NULL,
    parsed_requirements JSONB,
    embedding           VECTOR(1536), -- semantic embedding of job description
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Candidates profiles and parsed resume details
CREATE TABLE IF NOT EXISTS candidates (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT,
    email               TEXT,
    skills              TEXT[],
    experience_years    INT,
    resume_url          TEXT,
    parsed_resume       JSONB,
    embedding           VECTOR(1536), -- semantic embedding of resume text
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Evaluated matches between jobs and candidates
CREATE TABLE IF NOT EXISTS candidate_matches (
    job_id              UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id        UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    match_score         INT CHECK (match_score BETWEEN 0 AND 100),
    evaluation_report   JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (job_id, candidate_id)
);

CREATE INDEX IF NOT EXISTS idx_jobs_embedding ON jobs USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS idx_candidates_embedding ON candidates USING hnsw (embedding vector_cosine_ops);
