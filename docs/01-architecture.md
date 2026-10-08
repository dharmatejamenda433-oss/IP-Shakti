# IP-SAKTI — Architecture

Phase 0 deliverable. Describes *how* the system is structured. Technology choices are in
[`02-technology-stack.md`](02-technology-stack.md); rationale lives in [`decisions/`](decisions/).

---

## 1. Component overview

```
                    ┌────────────┐
   Internet ───────▶│   Nginx    │  TLS termination, reverse proxy, static frontend
                    └─────┬──────┘
                          │
                    ┌─────▼──────┐
                    │  FastAPI   │  /api/v1 — auth, documents, search, chat, audit
                    └─────┬──────┘
                          │
        ┌─────────────────▼─────────────────┐
        │  Auth / RBAC / Tenant Isolation    │  server-derived identity + tenant
        └─────────────────┬─────────────────┘
                          │
        ┌─────────────────▼─────────────────┐
        │        Application services        │
        │  ingestion · retrieval · generation│
        └───────┬───────────────────┬────────┘
                │                   │
        ┌───────▼──────┐    ┌───────▼──────┐
        │ PostgreSQL   │    │   Qdrant     │
        │ (system of   │    │ (vectors +   │
        │  record)     │    │  payloads)   │
        └──────────────┘    └──────────────┘

   ┌──────────────────────────────────────────────┐
   │ Python worker (python -m ipsakti.worker)       │
   │ polls ingestion_jobs → extract → chunk →       │
   │ embed → Qdrant upsert → update state           │
   └──────────────────────────────────────────────┘
                          │
                    ┌─────▼──────┐
                    │ Groq (ext) │  grounded generation only
                    └────────────┘
```

PostgreSQL is the **system of record**; Qdrant is a **derived, rebuildable index**. This keeps
DB/vector consistency recoverable and deletion safe.

---

## 2. Ingestion pipeline

```
POST /documents
  → authenticate → authorize (document:upload)
  → validate (type, MIME, magic bytes, size, filename safety)
  → store file (local FS, traversal-safe)
  → create document + document_version
  → create ingestion_job (UPLOADED)
  → return {document_id, job_id, status}

Worker loop:
  claim job (PROCESSING)
   → PDF extraction (PyMuPDF)         → EXTRACTED
   → structure-aware chunking         → CHUNKED
   → embedding (bge-small-en-v1.5)
   → Qdrant upsert (deterministic IDs)→ INDEXING
   → COMPLETED  (or FAILED, retryable)
```

The worker is **idempotent**: deterministic chunk IDs and deterministic Qdrant point IDs mean a
re-run upserts rather than duplicates. No Celery, no Redis — a plain polling Python worker.

---

## 3. Retrieval pipeline

```
User Query
  → authorize (search:execute) + resolve tenant
  → ┌ Dense retrieval (Qdrant, tenant-filtered) ┐
    └ BM25 retrieval (tenant-scoped index)      ┘
  → deduplicate by chunk_id
  → Reciprocal Rank Fusion   RRF(d) = Σ 1/(k + rank)      [k configurable]
  → Cross-Encoder reranking (bge-reranker-base, batched)  [pool 20–30 → final 5–8]
  → Relevance gate (configurable threshold)
       ├─ insufficient → controlled insufficient-evidence result (no LLM guess)
       └─ sufficient   → Context Builder
  → Context Builder emits numbered SOURCE [C#] blocks + citation_id → chunk → version → doc → page map
  → Groq (evidence-only prompt)
  → Citation validation (backend, conservative)
  → SSE stream (status · token · citation · error · done)
```

**Tenant filtering happens inside the Qdrant query and the BM25 index scope** — never
retrieve-all-then-filter.

---

## 4. Data model (initial)

| Table | Purpose |
| --- | --- |
| `tenants` | Isolation boundary; root of ownership |
| `users` | Authenticated identities, tenant members |
| `roles` | ADMIN / MANAGER / USER |
| `permissions` | document:upload, document:read, document:delete, search:execute, user:manage, audit:read |
| `user_roles` | user ↔ role (tenant-scoped) |
| `documents` | Logical document + provenance metadata |
| `document_versions` | Versioned content; every chunk belongs to a version |
| `document_chunks` | Chunk records (deterministic IDs, page/section metadata) |
| `ingestion_jobs` | State machine, attempt_count, error_message, timestamps |
| `audit_logs` | Immutable action log |

Chat persistence tables (`chat_sessions` / `chat_messages`) are **deferred** until chat
persistence is actually required.

Constraints: foreign keys, unique constraints, indexes, transactions, timestamps, status enums.

---

## 5. Security boundaries

- **Identity** — access/refresh tokens; tenant derived server-side from the authenticated principal, never from client input.
- **Authorization** — every protected route checks identity → tenant → role → permission → resource ownership.
- **Tenant isolation** — enforced at the DB query layer and the vector-search layer; direct ID manipulation returns a safe failure (no cross-tenant leakage, no oracle).
- **Storage** — traversal-safe filenames/paths; size caps; magic-byte validation.
- **Secrets** — environment only; never committed; never logged.

---

## 6. Application package layout (target — introduced Phase 2)

```
ipsakti/
  core/          # config, logging, request context, errors
  db/            # SQLAlchemy models, session, Alembic env
  auth/          # tokens, password hashing, RBAC, tenant resolution
  documents/     # upload, validation, storage, versioning
  ingestion/     # extraction, chunking, embedding, indexing
  retrieval/     # dense, bm25, rrf, rerank, relevance gate, context builder
  generation/    # provider.py, groq_provider.py, prompts.py, schemas.py
  citations/     # citation validation, provenance assembly
  audit/         # audit recording
  api/           # /api/v1 routers, dependencies, SSE
  worker.py      # python -m ipsakti.worker
```

The `generation/` package isolates the LLM provider so the rest of the app never depends on
Groq implementation details.

---

## 7. Deployment topology

Docker Compose services: `nginx`, `api` (FastAPI), `worker`, `postgres`, `qdrant`.
Persistent volumes for Postgres and Qdrant; health checks and restart policies on all services;
HTTPS at Nginx; documented DB backup strategy. Groq is an external dependency. No Kubernetes.
