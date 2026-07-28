# HR_AI: Multi-Agent AI Hiring Platform & Intelligent Router

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://python.langchain.com/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

An enterprise-grade AI Hiring Platform and Multi-Provider LLM Orchestrator built using **LangGraph**, **LangChain**, **FastAPI**, **PostgreSQL**, and **Redis**.

For a detailed portfolio breakdown and architectural walkthrough, see [PORTFOLIO_EXPLANATION.md](PORTFOLIO_EXPLANATION.md).

---

## Key Features

- **Multi-Agent Architecture**: Decoupled agents for resume parsing, job specification evaluation, candidate matching, and HR compliance auditing.
- **Resilient Multi-Provider LLM Router**: Dynamic fallback and tier switching across 6+ LLM backends (Google Gemini, OpenAI, Groq, Mistral AI, Cohere, Cerebras).
- **Automated DevOps & Sync Pipeline**: Background Python automation script (`scripts/auto_push.py`) with randomized cron delays, state deduplication tracking, and Conventional Commits generation.

---

## Quick Start

### 1. Install Dependencies & Setup Environment
```bash
uv sync
# or
pip install -r pyproject.toml
```

### 2. Run Main Entrypoint
```bash
python3 main.py
```

### 3. Run Automated Sync Script
```bash
python3 scripts/auto_push.py --no-delay
```

For full documentation and portfolio notes, read [PORTFOLIO_EXPLANATION.md](PORTFOLIO_EXPLANATION.md).
