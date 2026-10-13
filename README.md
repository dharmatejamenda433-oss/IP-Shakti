# IP-SAKTI

A production-oriented, **citation-grounded** AI knowledge and decision-support platform for
Ayurveda / traditional knowledge / intellectual-property / regulatory information.

Built for SIH problem statement **SIH26045**.

IP-SAKTI is **not** a generic chatbot, a LangChain demo, or an agent-framework demo.
It is an **AI-engineering + backend-engineering system** whose defining property is that
every answer is grounded in retrieved, provenance-tracked, tenant-authorized source evidence.

---

## Core capabilities

- Reliable PDF ingestion with page- and structure-aware extraction
- Structure-aware chunking with deterministic, version-scoped chunk IDs
- Hybrid retrieval: dense vectors (Qdrant) + BM25, fused with Reciprocal Rank Fusion
- Cross-encoder reranking with a configurable relevance gate
- Grounded generation via Groq with strict evidence-only prompting
- Backend citation validation and full answer → citation → chunk → version → source provenance
- Multi-tenant isolation, RBAC, and audit logging

---

## High-level architecture

```
Frontend → Nginx → FastAPI → Auth / RBAC / Tenant Isolation → Application services → PostgreSQL + Qdrant
```

```
Ingestion:  FastAPI → ingestion_jobs (PostgreSQL) → Python worker → PDF extraction → chunking → embedding → Qdrant
Retrieval:  Query → Dense + BM25 → RRF → Cross-Encoder Rerank → Relevance Gate → Context Builder → Groq → Citation Validation → SSE
```

Full details live in [`docs/`](docs/).

---

## Documentation index

| Document | Purpose |
| --- | --- |
| [`docs/00-requirements.md`](docs/00-requirements.md) | Functional & non-functional requirements |
| [`docs/01-architecture.md`](docs/01-architecture.md) | System architecture and data flow |
| [`docs/02-technology-stack.md`](docs/02-technology-stack.md) | Approved stack and prohibited technologies |
| [`docs/03-development-order.md`](docs/03-development-order.md) | Phase-by-phase delivery plan |
| [`docs/decisions/`](docs/decisions/) | Architecture Decision Records (ADRs) |

---

## Development model

This project is delivered **one phase at a time**. Each phase is implemented, tested,
reviewed, and committed before the next begins. See [`docs/03-development-order.md`](docs/03-development-order.md).

**Current status:** Phase 6 (PDF extraction) complete.

---

## Getting started (development)

Requires Python **3.12+** (3.13 verified). All commands run from the repository root.

```bash
# 1. Create and activate a virtual environment
python -m venv .venv
#    Windows (Git Bash):
.venv/Scripts/python.exe -m pip install --upgrade pip
#    Linux/macOS:
# source .venv/bin/activate && pip install --upgrade pip

# 2. Install the package with dev tooling
#    (Windows Git Bash uses .venv/Scripts/python.exe; Linux/macOS uses .venv/bin/python)
.venv/Scripts/python.exe -m pip install -e ".[dev]"

# 3. Copy the environment template and fill in secrets
cp .env.example .env

# 4. Run the quality gates
.venv/Scripts/python.exe -m ruff check .
.venv/Scripts/python.exe -m mypy ipsakti tests
.venv/Scripts/python.exe -m pytest
```

Optional dependency extras (installed on demand in later phases):

- `.[retrieval]` — PyMuPDF, rank-bm25, qdrant-client, sentence-transformers (Phases 6–14)
- `.[generation]` — Groq provider (Phase 16)

> **Phase 6 note:** PDF extraction only needs **PyMuPDF**. To avoid pulling the heavy
> ML stack (sentence-transformers/torch, needed from Phase 8) you can install it alone:
> `.venv/Scripts/python.exe -m pip install "pymupdf>=1.24,<2.0"`. PyMuPDF is imported
> lazily, so the rest of the app and the pure extraction helpers work without it.

---

## Repository layout

```
ipsakti/           # Application package (introduced in Phase 2)
data/corpus/       # Source documents — never committed (see .gitignore)
data/uploads/      # Transient upload landing zone — never committed
data/storage/      # Persisted document files — never committed
docs/              # Requirements, architecture, ADRs
tests/             # Unit / integration / API / security / E2E tests
pyproject.toml     # Dependencies, extras, ruff/mypy/pytest configuration
.env.example       # Environment template (copy to .env; never commit .env)
```
