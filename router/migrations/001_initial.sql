-- =============================================================================
-- HR AI Router: PostgreSQL Schema (001_initial.sql)
-- Based on the DB design in plan.md
-- Auto-applied by Docker on first startup via /docker-entrypoint-initdb.d/
-- =============================================================================

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMS
-- =============================================================================

CREATE TYPE provider_type_enum AS ENUM ('cloud', 'local', 'paid');

CREATE TYPE tier_enum AS ENUM (
    'PRIMARY_FREE',
    'SECONDARY_FREE',
    'LIMITED_FREE',
    'PAID',
    'LOCAL'
);

CREATE TYPE quota_type_enum AS ENUM (
    'REQUESTS',
    'TOKENS'
);

CREATE TYPE quota_window_enum AS ENUM (
    'SECOND',
    'MINUTE',
    'HOUR',
    'DAY',
    'MONTH',
    'LIFETIME',
    'CUSTOM'
);

CREATE TYPE reservation_state_enum AS ENUM (
    'pending',
    'completed',
    'released',
    'expired'
);

CREATE TYPE provider_event_type_enum AS ENUM (
    'rate_limit',
    'timeout',
    'server_error',
    'auth',
    'availability_change'
);

-- =============================================================================
-- 1. providers
-- Static provider-level information. Never mix with API keys.
-- =============================================================================
CREATE TABLE providers (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                TEXT UNIQUE NOT NULL,               -- e.g. "gemini", "groq"
    display_name        TEXT NOT NULL,
    provider_type       provider_type_enum NOT NULL,
    tier                tier_enum NOT NULL,
    priority            INTEGER NOT NULL DEFAULT 99,        -- lower = preferred
    enabled             BOOLEAN NOT NULL DEFAULT true,
    base_url            TEXT,
    supports_streaming  BOOLEAN NOT NULL DEFAULT false,
    supports_tools      BOOLEAN NOT NULL DEFAULT false,
    supports_images     BOOLEAN NOT NULL DEFAULT false,
    supports_reasoning  BOOLEAN NOT NULL DEFAULT false,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_providers_enabled ON providers(enabled);
CREATE INDEX idx_providers_tier ON providers(tier);

-- =============================================================================
-- 2. provider_credentials
-- API keys stored separately from provider metadata. Supports key rotation.
-- =============================================================================
CREATE TABLE provider_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    key_name        TEXT NOT NULL,                          -- e.g. "GEMINI_API_KEY"
    encrypted_key   TEXT NOT NULL,                          -- store encrypted in prod
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_provider_credentials_provider ON provider_credentials(provider_id, active);

-- =============================================================================
-- 3. models
-- Heart of the schema: per-model capabilities, tier, and status.
-- =============================================================================
CREATE TABLE models (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id         UUID NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
    model_name          TEXT NOT NULL,
    display_name        TEXT,
    tier                tier_enum NOT NULL,
    enabled             BOOLEAN NOT NULL DEFAULT true,
    context_window      INTEGER,
    max_output_tokens   INTEGER,
    -- capability flags
    vision              BOOLEAN NOT NULL DEFAULT false,
    tools               BOOLEAN NOT NULL DEFAULT false,
    reasoning           BOOLEAN NOT NULL DEFAULT false,
    embedding           BOOLEAN NOT NULL DEFAULT false,
    speech              BOOLEAN NOT NULL DEFAULT false,
    moderation          BOOLEAN NOT NULL DEFAULT false,
    coding              BOOLEAN NOT NULL DEFAULT false,
    chat                BOOLEAN NOT NULL DEFAULT true,
    -- round-robin tracking
    last_selected_at    TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(provider_id, model_name)
);

CREATE INDEX idx_models_provider ON models(provider_id);
CREATE INDEX idx_models_tier_enabled ON models(tier, enabled);
CREATE INDEX idx_models_last_selected ON models(last_selected_at ASC NULLS FIRST);

-- =============================================================================
-- 4. model_tags
-- Searchable capability tags. Router queries: WHERE tag = 'coding'
-- =============================================================================
CREATE TABLE model_tags (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id    UUID NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    tag         TEXT NOT NULL,
    UNIQUE(model_id, tag)
);

CREATE INDEX idx_model_tags_tag ON model_tags(tag);
CREATE INDEX idx_model_tags_model ON model_tags(model_id);

-- =============================================================================
-- 5. quota_definitions
-- Per-model quota limits across different windows. Quotas belong to models,
-- not providers (Mistral and OpenRouter have per-model limits).
-- =============================================================================
CREATE TABLE quota_definitions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id        UUID NOT NULL REFERENCES models(id) ON DELETE CASCADE,
    quota_type      quota_type_enum NOT NULL,
    quota_window    quota_window_enum NOT NULL,
    limit_value     BIGINT NOT NULL,                -- max tokens or requests
    timezone        TEXT NOT NULL DEFAULT 'UTC',
    resets_at       TIME,                           -- time of day for daily resets
    expires_at      TIMESTAMPTZ,                    -- for temporary quotas
    active          BOOLEAN NOT NULL DEFAULT true,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_quota_definitions_model ON quota_definitions(model_id, active);

-- =============================================================================
-- 6. quota_usage
-- Current window usage. Updated atomically on every request.
-- =============================================================================
CREATE TABLE quota_usage (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    quota_definition_id     UUID NOT NULL REFERENCES quota_definitions(id) ON DELETE CASCADE,
    used                    BIGINT NOT NULL DEFAULT 0,
    reserved                BIGINT NOT NULL DEFAULT 0,      -- in-flight reservations
    window_start            TIMESTAMPTZ NOT NULL,
    window_end              TIMESTAMPTZ NOT NULL,
    last_reset              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Critical index for quota check query
CREATE INDEX idx_quota_usage_definition_window ON quota_usage(quota_definition_id, window_end);
CREATE UNIQUE INDEX idx_quota_usage_active_window ON quota_usage(quota_definition_id, window_start);

-- =============================================================================
-- 7. reservations
-- In-flight request slots. Prevents race conditions in high-concurrency.
-- Consumed via SELECT FOR UPDATE SKIP LOCKED.
-- =============================================================================
CREATE TABLE reservations (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_uuid            UUID NOT NULL,
    model_id                UUID NOT NULL REFERENCES models(id),
    quota_definition_id     UUID NOT NULL REFERENCES quota_definitions(id),
    reserved_amount         BIGINT NOT NULL,
    state                   reservation_state_enum NOT NULL DEFAULT 'pending',
    expires_at              TIMESTAMPTZ NOT NULL DEFAULT (NOW() + INTERVAL '60 seconds'),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_reservations_model_state ON reservations(model_id, state);
CREATE INDEX idx_reservations_request ON reservations(request_uuid);
CREATE INDEX idx_reservations_expires ON reservations(expires_at) WHERE state = 'pending';

-- =============================================================================
-- 8. model_health
-- Pre-computed health state. Router reads this; never recalculates per request.
-- =============================================================================
CREATE TABLE model_health (
    model_id                UUID PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    healthy                 BOOLEAN NOT NULL DEFAULT true,
    average_latency         FLOAT,                          -- ms, rolling average
    average_ttft            FLOAT,                          -- time-to-first-token ms
    error_rate              FLOAT NOT NULL DEFAULT 0.0,     -- 0.0 to 1.0
    last_success            TIMESTAMPTZ,
    last_failure            TIMESTAMPTZ,
    consecutive_failures    INTEGER NOT NULL DEFAULT 0,
    disabled_until          TIMESTAMPTZ,                    -- circuit breaker cooldown
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_model_health_healthy ON model_health(healthy);
CREATE INDEX idx_model_health_disabled ON model_health(disabled_until) WHERE disabled_until IS NOT NULL;

-- =============================================================================
-- 9. routing_scores
-- Pre-computed 0-100 scores. Recalculated periodically, not per request.
-- =============================================================================
CREATE TABLE routing_scores (
    model_id            UUID PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    quality_score       FLOAT NOT NULL DEFAULT 50.0,
    speed_score         FLOAT NOT NULL DEFAULT 50.0,
    availability_score  FLOAT NOT NULL DEFAULT 50.0,
    cost_score          FLOAT NOT NULL DEFAULT 50.0,        -- 100 = free
    overall_score       FLOAT NOT NULL DEFAULT 50.0,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_routing_scores_overall ON routing_scores(overall_score DESC);

-- =============================================================================
-- 10. model_lifecycle
-- Date-awareness table. Handles temporary :free OpenRouter models,
-- deprecated models, and replacement tracking.
-- =============================================================================
CREATE TABLE model_lifecycle (
    model_id                UUID PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    introduced_at           DATE,
    deprecated_at           DATE,
    expires_at              TIMESTAMPTZ,                    -- after this: stop routing
    last_verified_at        TIMESTAMPTZ,
    verification_source     TEXT,                           -- "providers.yaml", "api", "manual"
    replacement_model_id    UUID REFERENCES models(id)
);

CREATE INDEX idx_model_lifecycle_expires ON model_lifecycle(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_model_lifecycle_deprecated ON model_lifecycle(deprecated_at) WHERE deprecated_at IS NOT NULL;

-- =============================================================================
-- 11. model_availability
-- Real-time availability flag. Some OpenRouter models disappear without warning.
-- =============================================================================
CREATE TABLE model_availability (
    model_id        UUID PRIMARY KEY REFERENCES models(id) ON DELETE CASCADE,
    available       BOOLEAN NOT NULL DEFAULT true,
    expires_at      TIMESTAMPTZ,
    last_checked    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    notes           TEXT
);

CREATE INDEX idx_model_availability_available ON model_availability(available);
CREATE INDEX idx_model_availability_expires ON model_availability(expires_at) WHERE expires_at IS NOT NULL;

-- =============================================================================
-- 12. request_log
-- Append-only log. Every request recorded for analytics.
-- =============================================================================
CREATE TABLE request_log (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    request_uuid        UUID NOT NULL,
    provider_id         UUID REFERENCES providers(id),
    model_id            UUID REFERENCES models(id),
    status              TEXT NOT NULL,                      -- "success", "failure", "retry"
    prompt_tokens       INTEGER,
    completion_tokens   INTEGER,
    total_tokens        INTEGER,
    latency_ms          INTEGER,
    ttft_ms             INTEGER,
    http_status         INTEGER,
    error_message       TEXT,
    attempt             INTEGER NOT NULL DEFAULT 1,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_request_log_request ON request_log(request_uuid);
CREATE INDEX idx_request_log_model ON request_log(model_id, created_at DESC);
CREATE INDEX idx_request_log_created ON request_log(created_at DESC);

-- =============================================================================
-- 13. provider_events
-- Outage and event tracking per provider.
-- =============================================================================
CREATE TABLE provider_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_id     UUID NOT NULL REFERENCES providers(id),
    event_type      provider_event_type_enum NOT NULL,
    message         TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_provider_events_provider ON provider_events(provider_id, created_at DESC);

-- =============================================================================
-- HELPER FUNCTION: auto-update updated_at timestamp
-- =============================================================================
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_providers_updated_at
    BEFORE UPDATE ON providers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

CREATE TRIGGER trg_models_updated_at
    BEFORE UPDATE ON models
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();
