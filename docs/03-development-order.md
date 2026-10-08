# IP-SAKTI — Development Order

Phase 0 deliverable. The project is delivered **one phase at a time**. Each phase is implemented,
tested, reviewed, and committed before the next begins.

---

## Execution rule (applies to every phase)

For "Implement Phase X":

1. Inspect the repository and current files.
2. Identify what already exists.
3. Implement **only** Phase X — never Phase X+1.
4. Do not rewrite unrelated code; do not delete existing functionality unless required.
5. Preserve existing tests; add tests for the current phase.
6. Run the relevant tests; fix failures caused by the implementation.
7. Perform a basic security/design review and check backward compatibility.
8. Summarize exactly what changed; list files created/modified; state tests executed and results.
9. **STOP.** Wait for the next instruction.

Suggested commit tags: `phase-00-requirements`, `phase-01-foundation`, `phase-02-architecture`,
`phase-03-database`, … one logical commit per phase.

---

## Phase plan

| Phase | Title | Primary output |
| --- | --- | --- |
| **0** | Requirements & architecture | ✅ This documentation set |
| **1** | Repository / environment / foundation | Project scaffold, tooling (ruff/mypy/pytest), config, env, git/CI hygiene |
| **2** | Application structure | `ipsakti/` package layout, core (config, logging, errors, request context) |
| **3** | PostgreSQL / Alembic | SQLAlchemy 2.x models, migrations, initial tables |
| **4** | Authentication / RBAC / tenant isolation | Tokens, hashing, roles, permissions, tenant enforcement |
| **5** | Document upload | `POST /documents`, validation, storage, version + job creation |
| **6** | PDF extraction | PyMuPDF page/section-aware extraction, failure handling |
| **7** | Structure-aware chunking | Recursive chunker, deterministic IDs, metadata |
| **8** | Embeddings | bge-small-en-v1.5 via Sentence Transformers, batching |
| **9** | Qdrant | Collection, payload, tenant-filtered search, idempotent upserts |
| **10** | Worker | `python -m ipsakti.worker`, state machine, retry, idempotency |
| **11** | Dense retrieval | Query embedding + tenant-filtered vector search |
| **12** | BM25 | rank-bm25 index, search, rebuild |
| **13** | Hybrid retrieval / RRF | Dedup + Reciprocal Rank Fusion |
| **14** | Cross-encoder reranking | bge-reranker-base, relevance gate |
| **15** | Retrieval evaluation | Gold dataset, Recall@5/@10, MRR across strategies |
| **16** | Groq generation | Provider isolation, evidence-only prompts |
| **17** | Citations / grounding | Backend citation validation, provenance assembly |
| **18** | Domain intelligence | Deterministic metadata + filters (jurisdiction/domain/type/indicators) |
| **19** | SSE chat | Streaming events, disconnect/failure handling |
| **20** | Audit / observability | Audit log, structured logging, latency metrics |
| **21** | Complete testing | Unit/integration/API/security/E2E coverage |
| **22** | Minimal frontend | Login, dashboard, documents, upload, status, search, chat, citations |
| **23** | Docker | Compose services, volumes, health checks |
| **24** | Deployment | Nginx + HTTPS, persistence, backups, restart policies |
| **25** | CI/CD | GitHub Actions: ruff, type check, pytest, docker build |
| **26** | Final evaluation | Retrieval + generation evaluation, measured latency, quality bar |

---

## Final quality bar

IP-SAKTI must ultimately demonstrate: strong tenant isolation · correct RBAC · reliable ingestion ·
page-aware extraction · structure-aware chunking · strong dense retrieval · strong BM25 · hybrid RRF ·
cross-encoder reranking · retrieval evaluation · grounded generation · citation validation ·
version-aware provenance · insufficient-evidence abstention · reliable idempotent worker ·
comprehensive testing · measured latency · Docker deployment · CI/CD.

Depth and measurable behavior — **not** excessive infrastructure.
