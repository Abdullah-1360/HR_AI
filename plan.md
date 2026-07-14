I would not design this as a simple "providers/models" database. You're essentially building a **distributed LLM scheduler**, so the database should model four separate concerns:

1. **Provider configuration** (static)
2. **Model capabilities** (static)
3. **Quota windows** (dynamic)
4. **Routing/health state** (dynamic)

Keeping these concerns separate makes the router much easier to evolve as providers change quotas or add models.

---

# Overall Architecture

```
Provider
    │
    ├── API Keys
    │
    ├── Models
    │       │
    │       ├── Capabilities
    │       ├── Quotas
    │       └── Health
    │
    └── Requests
            │
            └── Token Usage
```

Notice that **quotas belong to models, not providers**, because OpenRouter and Mistral expose different limits per model.

---

# 1. providers

Only provider-level information.

```sql
providers
---------
id                  UUID
name                TEXT UNIQUE
display_name        TEXT

provider_type       ENUM
(
    cloud,
    local,
    paid
)

priority            INTEGER

enabled             BOOLEAN

base_url            TEXT

supports_streaming  BOOLEAN
supports_tools      BOOLEAN
supports_images     BOOLEAN
supports_reasoning  BOOLEAN

created_at
updated_at
```

Examples

```
Gemini
Groq
OpenRouter
Mistral
Cerebras
OpenAI
Local
```

---

# 2. provider_credentials

Never mix API keys with provider metadata.

```sql
provider_credentials

id

provider_id

key_name

encrypted_key

active

created_at
```

Allows key rotation later.

---

# 3. models

This is the heart.

```
models

id

provider_id

model_name

display_name

tier

status

context_window

max_output_tokens

vision

tools

reasoning

embedding

speech

moderation

coding

chat

created_at
updated_at
```

Example

```
gemini-2.5-flash

tier = FREE

context = 1,048,576

vision = true

tools = true

reasoning = true
```

---

# 4. model_tags

Instead of dozens of booleans.

```
model_tags

id

model_id

tag
```

Example

```
reasoning

vision

tool-calling

coding

embedding

small

fast

cheap

large-context
```

Router becomes easier.

```
Need coding?

SELECT *

WHERE tag='coding'
```

---

# 5. quota_definitions

Most important table.

```
quota_definitions

id

model_id

quota_type

limit_value

window

timezone

resets_at

active
```

quota_type

```
REQUESTS

TOKENS

```

window

```
SECOND

MINUTE

HOUR

DAY

MONTH

CUSTOM
```

Example

```
model

mistral-small

quota

TOKENS

window

MINUTE

2250000
```

Another row

```
REQUESTS

SECOND

5
```

OpenRouter temporary model

```
Requests

DAY

1000

expires

2026-07-21
```

Notice expiry belongs here.

---

# 6. quota_usage

Current usage only.

```
quota_usage

id

quota_definition_id

used

reserved

window_start

window_end

last_reset
```

Example

```
RPM

used

12

reserved

1

window

12:31
```

---

# 7. model_health

Never calculate health every request.

```
model_health

model_id

healthy

average_latency

average_ttft

error_rate

last_success

last_failure

consecutive_failures

disabled_until
```

Router simply reads it.

---

# 8. routing_scores

Instead of recalculating scores constantly.

```
routing_scores

model_id

quality_score

speed_score

availability_score

cost_score

overall_score

updated_at
```

Scores 0-100.

---

# 9. request_log

Every request.

```
request_log

id

request_uuid

provider_id

model_id

status

prompt_tokens

completion_tokens

total_tokens

latency_ms

http_status

created_at
```

---

# 10. reservations

Critical for concurrency.

```
reservations

id

request_uuid

model_id

quota_definition_id

reserved_amount

expires_at

state

pending

completed

released
```

Without this you'll have race conditions.

---

# 11. provider_events

Track outages.

```
provider_events

provider_id

type

rate_limit

timeout

server_error

auth

message

created_at
```

Useful later.

---

# 12. model_availability

Some OpenRouter models disappear.

```
model_availability

model_id

available

expires_at

last_checked

notes
```

For example

```
Tencent HY3

expires

2026-07-21
```

After that

```
available=false
```

Router ignores it.

---

# Routing tiers

I wouldn't use FREE vs PAID.

I'd use routing tiers.

```
tier

PRIMARY_FREE

SECONDARY_FREE

LIMITED_FREE

PAID

LOCAL
```

Example

```
Gemini

PRIMARY_FREE

Groq

PRIMARY_FREE

OpenRouter

SECONDARY_FREE

Mistral

SECONDARY_FREE

Cerebras

LIMITED_FREE

OpenAI

PAID

Local

LOCAL
```

Router can simply

```
PRIMARY

↓

SECONDARY

↓

LIMITED

↓

PAID

↓

LOCAL
```

---

# How middleware works

```
Incoming Request

↓

Estimate Prompt Tokens

↓

Find Required Features
    vision?
    tools?
    reasoning?
    coding?

↓

Find Eligible Models

↓

Filter
    enabled
    available
    not expired
    healthy
    quota remaining

↓

Reserve quota

↓

Call Provider

↓

Success
    Update usage
    Update latency
    Update health

↓

Failure
    Release reservation
    Increase failure count
    Retry next model
```

---

# The selector query

The scheduler should never iterate through providers in code. Instead, ask the database for the best candidate.

Conceptually, the query is:

```
SELECT model
FROM models
JOIN model_health
JOIN routing_scores
JOIN quota_usage
JOIN quota_definitions
JOIN model_availability
WHERE
    enabled = true
    AND healthy = true
    AND available = true
    AND expires_at > NOW()
    AND quota_remaining >= estimated_tokens
    AND supports_requested_features = true
ORDER BY
    tier ASC,
    overall_score DESC,
    availability_score DESC,
    latency ASC
LIMIT 1;
```

The middleware then reserves quota, makes the API call, updates usage and health, and repeats the selection only if the request fails.

---

## One additional table I'd add

Given your goal of being "fully date aware," I'd add a `model_lifecycle` table separate from quotas:

```
model_lifecycle
---------------
model_id
introduced_at
deprecated_at
expires_at
last_verified_at
verification_source
replacement_model_id
```

This lets your router gracefully handle temporary models (such as OpenRouter's `:free` offerings that expire on a specific date) without deleting records. The scheduler can automatically stop considering models whose `expires_at` has passed, while preserving historical request logs and usage statistics.

With this schema, adding a new provider—or accommodating changes in quotas, context windows, or model availability—becomes a data update rather than a code change. Your routing logic remains generic and operates entirely on the database's view of provider capabilities, quotas, health, and lifecycle.
