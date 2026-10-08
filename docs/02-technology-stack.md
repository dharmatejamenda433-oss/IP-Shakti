# IP-SAKTI — Technology Stack

Phase 0 deliverable. The approved stack and the explicitly prohibited technologies.

---

## 1. Approved stack

| Layer | Choice | Notes |
| --- | --- | --- |
| Language | **Python 3.12** | Typed throughout |
| API | **FastAPI** | `/api/v1` |
| Validation | **Pydantic** | Schemas at boundaries |
| ORM | **SQLAlchemy 2.x** | 2.0-style typed models |
| Migrations | **Alembic** | Versioned schema |
| System DB | **PostgreSQL** | System of record |
| Vector store | **Qdrant** | Collection `ipsakti_chunks`, dim 384, Cosine |
| PDF extraction | **PyMuPDF** | No OCR initially |
| Embeddings | **Sentence Transformers** + **BAAI/bge-small-en-v1.5** | 384-dim, cosine, batched, local (no paid APIs) |
| Lexical retrieval | **rank-bm25** | In-process BM25 |
| Reranking | **BAAI/bge-reranker-base** | Cross-encoder, batched |
| Generation | **Groq API** | Isolated behind provider interface |
| Streaming | **SSE** | Chat responses |
| Testing | **pytest** | Unit / integration / API / security / E2E |
| Lint | **Ruff** | |
| Type check | **mypy** or **pyright** | |
| Containers | **Docker**, **Docker Compose** | No Kubernetes |
| Proxy | **Nginx** | TLS, reverse proxy |
| CI/CD | **GitHub Actions** | ruff, type check, pytest, docker build |

---

## 2. Configuration principles

- Embedding model name, reranker model name, Groq model name → **configurable via environment/config**, never hard-coded across the codebase.
- Tunables (chunk size/overlap, RRF `k`, candidate pool, final result count, relevance threshold) → **configuration**, not magic constants.
- API keys and secrets → **environment variables only**; never committed.

---

## 3. Prohibited technologies

Do **not** introduce any of the following. Adding one requires explicit approval and a documented
technical justification (see [`decisions/`](decisions/)).

LangChain · LangGraph · Redis · Celery · Kafka · Kubernetes · Elasticsearch · OpenSearch ·
LangSmith · Langfuse · RAGAS · microservices · service mesh · API gateway ·
pervasive event-driven architecture · unnecessary message brokers · unnecessary vector databases ·
unnecessary orchestration frameworks.

**Guiding rule:** do not replace simple, explicit Python code with a framework merely for
abstraction or popularity.
