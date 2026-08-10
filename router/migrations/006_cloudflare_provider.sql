-- =============================================================================
-- HR AI Router: Migration 006 - Add Cloudflare AI Provider & Models
-- Cloudflare Workers AI OpenAI-compatible endpoint
-- Base URL: https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/ai/v1
-- =============================================================================

-- -----------------------------------------------------------------------
-- 1. Insert Cloudflare AI provider
-- -----------------------------------------------------------------------
INSERT INTO providers (
    name, display_name, provider_type, tier, priority, enabled,
    base_url, supports_streaming, supports_tools, supports_images, supports_reasoning
) VALUES (
    'cloudflare',
    'Cloudflare Workers AI',
    'cloud',
    'PRIMARY_FREE',
    20,  -- higher priority than default (lower number = preferred)
    true,
    'https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/ai/v1',
    true,
    true,
    true,
    true
);

-- -----------------------------------------------------------------------
-- 2. Insert Cloudflare AI models
-- -----------------------------------------------------------------------

-- @zai-org/glm-4.7-flash
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/zai-org/glm-4.7-flash', 'GLM-4.7 Flash (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, false, true, false, false, true
FROM providers p WHERE p.name = 'cloudflare';

-- @qwen/qwen3-30b-a3b-fp8
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/qwen/qwen3-30b-a3b-fp8', 'Qwen3 30B A3B FP8 (Cloudflare)',
    'PRIMARY_FREE', true,
    40960, 8192, false, true, true, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @google/gemma-4-26b-a4b-it
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/google/gemma-4-26b-a4b-it', 'Gemma 4 26B A4B IT (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, true, true, false, false, true
FROM providers p WHERE p.name = 'cloudflare';

-- @openai/gpt-oss-20b
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/openai/gpt-oss-20b', 'GPT OSS 20B (Cloudflare)',
    'PRIMARY_FREE', true,
    128000, 16384, false, true, false, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @openai/gpt-oss-120b
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/openai/gpt-oss-120b', 'GPT OSS 120B (Cloudflare)',
    'SECONDARY_FREE', true,
    128000, 16384, false, true, true, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @nvidia/nemotron-3-120b-a12b (reasoning heavy)
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/nvidia/nemotron-3-120b-a12b', 'Nemotron 3 120B A12B (Cloudflare)',
    'SECONDARY_FREE', true,
    131072, 8192, false, false, true, false, true
FROM providers p WHERE p.name = 'cloudflare';

-- @meta/llama-4-scout-17b-16e-instruct
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/meta/llama-4-scout-17b-16e-instruct', 'Llama 4 Scout 17B (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, true, true, false, false, true
FROM providers p WHERE p.name = 'cloudflare';

-- @meta/llama-3.3-70b-instruct-fp8-fast
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/meta/llama-3.3-70b-instruct-fp8-fast', 'Llama 3.3 70B FP8 Fast (Cloudflare)',
    'PRIMARY_FREE', true,
    128000, 8192, false, true, false, false, true
FROM providers p WHERE p.name = 'cloudflare';

-- @qwen/qwen2.5-coder-32b-instruct
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/qwen/qwen2.5-coder-32b-instruct', 'Qwen2.5 Coder 32B (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, false, true, false, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @qwen/qwq-32b (reasoning model)
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/qwen/qwq-32b', 'QwQ 32B (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, false, false, true, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @mistralai/mistral-small-3.1-24b-instruct
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/mistralai/mistral-small-3.1-24b-instruct', 'Mistral Small 3.1 24B (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, true, true, false, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- @ibm-granite/granite-4.0-h-micro
INSERT INTO models (provider_id, model_name, display_name, tier, enabled,
    context_window, max_output_tokens, vision, tools, reasoning, coding, chat)
SELECT p.id,
    '@cf/ibm-granite/granite-4.0-h-micro', 'Granite 4.0 H Micro (Cloudflare)',
    'PRIMARY_FREE', true,
    131072, 8192, false, true, false, true, true
FROM providers p WHERE p.name = 'cloudflare';

-- -----------------------------------------------------------------------
-- 3. Bootstrap model_health for all new Cloudflare models
-- -----------------------------------------------------------------------
INSERT INTO model_health (model_id, healthy, error_rate, consecutive_failures)
SELECT m.id, true, 0.0, 0
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
ON CONFLICT (model_id) DO NOTHING;

-- -----------------------------------------------------------------------
-- 4. Bootstrap routing_scores for all new Cloudflare models
-- -----------------------------------------------------------------------
INSERT INTO routing_scores (model_id, quality_score, speed_score, availability_score, cost_score, overall_score)
SELECT m.id,
    70.0,   -- quality_score  (good, solid open-source models)
    80.0,   -- speed_score    (Cloudflare edge = very fast inference)
    75.0,   -- availability_score
    100.0,  -- cost_score     (free tier via Cloudflare Workers AI)
    81.25   -- overall_score  = avg of above
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
ON CONFLICT (model_id) DO NOTHING;

-- -----------------------------------------------------------------------
-- 5. Bootstrap model_availability for all new Cloudflare models
-- -----------------------------------------------------------------------
INSERT INTO model_availability (model_id, available)
SELECT m.id, true
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
ON CONFLICT (model_id) DO NOTHING;

-- -----------------------------------------------------------------------
-- 6. Bootstrap model_lifecycle for all new Cloudflare models
-- -----------------------------------------------------------------------
INSERT INTO model_lifecycle (model_id, introduced_at, verification_source)
SELECT m.id, CURRENT_DATE, 'manual'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
ON CONFLICT (model_id) DO NOTHING;

-- -----------------------------------------------------------------------
-- 7. Add model_tags for key capability-based routing
-- -----------------------------------------------------------------------

-- Reasoning models
INSERT INTO model_tags (model_id, tag)
SELECT m.id, 'reasoning'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
  AND m.model_name IN (
    '@cf/qwen/qwq-32b',
    '@cf/nvidia/nemotron-3-120b-a12b',
    '@cf/openai/gpt-oss-120b',
    '@cf/qwen/qwen3-30b-a3b-fp8'
  )
ON CONFLICT (model_id, tag) DO NOTHING;

-- Coding models
INSERT INTO model_tags (model_id, tag)
SELECT m.id, 'coding'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
  AND m.model_name IN (
    '@cf/qwen/qwen2.5-coder-32b-instruct',
    '@cf/openai/gpt-oss-20b',
    '@cf/openai/gpt-oss-120b',
    '@cf/ibm-granite/granite-4.0-h-micro',
    '@cf/qwen/qwen3-30b-a3b-fp8'
  )
ON CONFLICT (model_id, tag) DO NOTHING;

-- Vision models
INSERT INTO model_tags (model_id, tag)
SELECT m.id, 'vision'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
  AND m.model_name IN (
    '@cf/google/gemma-4-26b-a4b-it',
    '@cf/meta/llama-4-scout-17b-16e-instruct',
    '@cf/mistralai/mistral-small-3.1-24b-instruct'
  )
ON CONFLICT (model_id, tag) DO NOTHING;

-- Fast inference models
INSERT INTO model_tags (model_id, tag)
SELECT m.id, 'fast'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
  AND m.model_name IN (
    '@cf/meta/llama-3.3-70b-instruct-fp8-fast',
    '@cf/zai-org/glm-4.7-flash',
    '@cf/ibm-granite/granite-4.0-h-micro'
  )
ON CONFLICT (model_id, tag) DO NOTHING;

-- General chat tag for all Cloudflare models
INSERT INTO model_tags (model_id, tag)
SELECT m.id, 'chat'
FROM models m
JOIN providers p ON p.id = m.provider_id
WHERE p.name = 'cloudflare'
ON CONFLICT (model_id, tag) DO NOTHING;
