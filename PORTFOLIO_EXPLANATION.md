# HR_AI: Industry-Grade Multi-Agent AI Hiring Platform & Automated DevOps Pipeline

> **Portfolio Showcase & Project Deep Dive**  
> **Technologies:** Python 3.11+, LangGraph, LangChain, FastAPI, PostgreSQL, Redis, Multi-LLM Routing (Gemini, OpenAI, Groq, Mistral, Cohere, Cerebras), Git Automation, Linux Cron.

---

## 1. Executive Summary

**HR_AI** is an enterprise-grade AI Hiring & Candidate Evaluation Platform engineered to automate and optimize recruitment workflows. Built upon a **LangGraph multi-agent architecture**, HR_AI transitions away from naive single-LLM implementations to an autonomous, resilient multi-provider orchestration system.

In addition to core hiring intelligence, HR_AI features an **Automated DevOps Synchronization Pipeline**—a self-contained background engine (`scripts/auto_push.py`) that performs intelligent, state-tracked, and stealth-scheduled code commits and repository pushes.

---

## 2. Platform Architecture

```
                               ┌──────────────────────────────┐
                               │       Frontend UI            │
                               │     React / Next.js          │
                               └─────────────┬────────────────┘
                                             │ REST / API Gateway
                               ┌─────────────▼────────────────┐
                               │       FastAPI Backend        │
                               │ Authentication & Middleware  │
                               └─────────────┬────────────────┘
                                             │
                       ┌─────────────────────┴─────────────────────┐
                       │                                           │
             ┌─────────▼───────────┐                     ┌─────────▼───────────┐
             │  PostgreSQL / Redis │                     │ Object / File Store │
             │ Job & Candidate DB  │                     │ Resumes & Artifacts │
             └─────────────────────┘                     └─────────────────────┘
                                             │
                              LangGraph Multi-Agent Orchestrator
                                             │
       ┌─────────────────────────────────────┴─────────────────────────────────────┐
       │                                                                           │
┌──────▼──────┐   ┌─────────────┐   ┌─────────────┐   ┌─────────────┐   ┌──────────▼────────┐
│ Resume      │   │ Job Specs   │   │ Candidate   │   │ HR Policy   │   │ Multi-Provider    │
│ Parser      │   │ Evaluator   │   │ Matcher     │   │ & Audit     │   │ Router Engine     │
└─────────────┘   └─────────────┘   └─────────────┘   └─────────────┘   └──────────┬────────┘
                                                                                   │
                                                          ┌────────────────────────┴────────────────────────┐
                                                          │ Gemini │ OpenAI │ Groq │ Mistral │ Cohere │ Cerebras │
                                                          └─────────────────────────────────────────────────┘
```

---

## 3. Key Technical Innovations

### 3.1 Multi-Agent LangGraph Workflow Engine
- **Decoupled Agent Topology:** Specialized agents handle distinct steps (resume parsing, job description analysis, candidate scoring, and policy compliance).
- **Stateful Execution Graph:** Built using `langgraph.graph.StateGraph` for predictable state propagation, execution history tracking, and intermediate checkpoints.

### 3.2 Multi-Provider LLM Fallback & Router (`graph.py` & `router/`)
- **Resilient Multi-LLM Orchestration:** Automatically routes requests across **6+ LLM providers** (Google Gemini, OpenAI, Groq, Mistral AI, Cohere, Cerebras).
- **Dynamic Retry & Tier Switching:** If a provider hits rate limits (429) or downtime (5xx), the execution graph seamlessly transitions to fallback models without dropping candidate evaluation state (`after_llm` conditional edges).
- **Cost & Latency Optimization:** Directs low-complexity tasks (e.g. initial filtering) to fast inference providers (Groq/Cerebras) while reserving frontier models (GPT-4o/Gemini 2.5) for complex reasoning tasks.

### 3.3 Automated CI/CD & Repository Sync Engine (`scripts/auto_push.py`)
To maintain continuous integration, automate repository updates, and manage staged releases, HR_AI includes an intelligent automated synchronization tool:

- **Stealth Randomization Scheduling:** Runs on an 8-hour cron cycle with a randomized jitter delay (0–180 minutes) to prevent predictable, detectible batch execution signatures.
- **State-Aware History Tracking (`.pushed_history.json`):** Tracks every file pushed to prevent duplicate submissions or unintended re-pushes.
- **Semantic Conventional Commits Generator:** Dynamically generates standard commit messages based on file scope and type (e.g., `feat(app): add main.py module`, `docs: update README.md`, `chore(scripts): update configuration`).
- **Granular Git Staging:** Staging, committing, and pushing occur one file at a time, ensuring modular commit histories.

---

## 4. Repository & File Structure

```
HR_AI/
├── app/                      # Main application modules
├── router/                   # Multi-provider routing engine & DB logic
│   ├── db.py                 # PostgreSQL connection pool & schema utilities
│   └── router_node.py        # LangGraph routing node implementation
├── scripts/                  # Utilities & DevOps scripts
│   ├── auto_push.py          # Automated stealth GitHub sync engine
│   ├── .pushed_history.json  # Persistence state for auto-push pipeline
│   └── bulk_upload.py        # Bulk dataset ingestion pipeline
├── tests/                    # Comprehensive unit and integration test suite
├── graph.py                  # LangGraph core workflow graph & state schema
├── main.py                   # FastAPI app entrypoint & provider verification
├── plan.md                   # System architectural specifications
├── pyproject.toml            # Dependencies & build configuration
└── docker-compose.yml        # Multi-container orchestration (DB, Cache, App)
```

---

## 5. Technical Demonstration & Usage

### Running the Multi-Provider Router Test
```bash
# Verify all configured LLM provider connections and test routing graph
python3 main.py
```

### Running the Automated DevOps Sync Engine
```bash
# Run manual execution without randomized delay
python3 scripts/auto_push.py --no-delay

# Schedule background execution via Cron (Every 8 Hours with Random Delay)
0 */8 * * * /usr/bin/python3 /home/ubuntu/HR_AI/scripts/auto_push.py >> /home/ubuntu/HR_AI/scripts/auto_push.log 2>&1
```

---

## 6. Portfolio Highlights for Hiring Managers

- **Production-Grade Resilience:** Solves real-world LLM API instability through automated fallback graphs.
- **Full-Stack Engineering:** Combines graph-based AI agent design with robust backend database pooling (PostgreSQL), task queues (Redis), and REST APIs.
- **DevOps Automation Mastery:** Demonstrates deep proficiency with Linux systems, Python subprocess management, Git workflow automation, and stealth scheduling logic.
