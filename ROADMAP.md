# HR AI Platform - Industry-Grade Architecture Roadmap & Implementation Specs

This document serves as the single source of truth for the evolution of the HR AI Platform from prototype to an enterprise-grade AI Recruitment Operating System.

---

## Overall System Architecture

```
                             ┌──────────────────────────────────────┐
                             │       Frontend (Next.js 15)          │
                             └──────────────────┬───────────────────┘
                                                │ REST / WebSockets / SSE
                             ┌──────────────────▼───────────────────┐
                             │     API Gateway / FastAPI Backend    │
                             │  (Tenant Isolation & JWT Auth)       │
                             └──────────┬─────────────────┬─────────┘
                                        │                 │
            ┌───────────────────────────┴───┐         ┌───▼───────────────────────────┐
            │   Async Task Queue (ARQ /     │         │   Multi-Provider LLM Router   │
            │   Redis Background Workers)   │         │   (Fallback, Quota & Telemetry)   │
            └───────────────┬───────────────┘         └───────────────┬───────────────┘
                            │                                         │
 ┌──────────────────────────▼─────────────────────────────────────────▼─────────────────────────┐
 │                            LangGraph Orchestrator & State Checkpoints                          │
 │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐    ┌────────────────────┐   │
 │  │ Blind Screening │ ──►│ Hybrid Search   │ ──►│ Candidate Match │ ──►│ Human-in-the-Loop  │   │
 │  │ Agent (DEI)     │    │ (pgvector+BM25) │    │ & Reranker      │    │ Recruiter Approval │   │
 │  └─────────────────┘    └─────────────────┘    └─────────────────┘    └────────────────────┘   │
 └────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## Phased Implementation Roadmap

### Phase 1: Core System Stability & Search Quality (Immediate Focus)
1. **Hybrid Vector Search & Re-ranking (pgvector + BM25 + Cohere Rerank)**
   - Combine dense embedding cosine similarity (`pgvector`) with sparse lexical full-text search (`tsvector`) using Reciprocal Rank Fusion (RRF).
   - Add optional secondary re-ranking stage using Cohere Rerank v3.
2. **Asynchronous Background Processing (ARQ / Redis Task Queue)**
   - Offload heavy PDF parsing, OCR, vector embedding generation, and bulk resume ingestion to background task workers.
   - Provide job status endpoints with progress tracking for frontend polling/SSE.
3. **Multi-Tenancy & Authentication Foundations**
   - Add `tenant_id` to database tables (`jobs`, `candidates`, `matches`, `interviews`).
   - Implement JWT authentication verification and dependency injection in FastAPI ([app/deps.py](file:///home/ubuntu/HR_AI/app/deps.py)).

---

### Phase 2: AI Intelligence, Compliance & Observability
1. **LangGraph Human-in-the-Loop (HITL) Checkpoints**
   - Use `AsyncPostgresSaver` checkpointer for state persistence.
   - Pause agent execution at key decisions (e.g., candidate shortlist approval, match threshold tuning) for recruiter confirmation.
2. **Blind Resume Screening Agent (DEI & Compliance)**
   - Create an Anonymization Agent node that strips PII (Name, Age, Address, Gender, University Name) prior to evaluation.
3. **Observability & Telemetry Integration**
   - Integrate LangSmith / LangFuse tracing across LangChain / LangGraph chains and custom provider router calls.

---

### Phase 3: Open-Source Enterprise Integrations & AI Agent Expansion (Free-Tier & OpenAI Supported)
1. **Self-Hosted ATS & HRIS Webhook Receivers (Open-Source)**
   - Inbound webhook receivers for Greenhouse, Lever, and custom ATS platforms (zero paid unified API dependencies like Merge.dev/Finch).
2. **Conversational Recruiter Copilot Enhancements**
   - Natural language search over candidate pools powered by OpenAI (`gpt-4o-mini`) or free-tier providers (Gemini / Groq).
3. **AI Voice/Audio Screening Agent (OpenAI Whisper + Browser Web Speech API)**
   - Candidate screening voice/text agent using OpenAI's Audio API / Whisper (open-source) + Web Speech API (free in browser).


---

*Last Updated: July 2026*
