# ADR 0001 — PostgreSQL as system of record, Qdrant as derived index

**Status:** Accepted

## Context
The system stores documents, versions, chunks, ingestion jobs, users, tenants, and audit logs, and
also needs vector search. Two stores are involved: PostgreSQL and Qdrant. We need a clear rule for
which store is authoritative so that failures, reindexing, and deletions stay consistent.

## Decision
PostgreSQL is the **system of record** for all documents, versions, chunk metadata, ingestion state,
identity, and audit. Qdrant holds a **derived, rebuildable** vector index (`ipsakti_chunks`, dim 384,
Cosine) whose points reference PostgreSQL-owned deterministic IDs.

Rules that follow:
- Every Qdrant point carries `chunk_id`, `document_id`, `version_id`, `tenant_id`, and provenance payload.
- Qdrant point IDs are deterministic and derived from chunk IDs → upserts are idempotent.
- The index can be fully rebuilt from PostgreSQL + stored files without data loss.
- Deletion removes DB rows and the corresponding Qdrant points; no orphaned searchable vectors remain.

## Consequences
- **Positive:** DB/vector consistency is recoverable; reindex and repair are straightforward; no dual-write ambiguity about truth.
- **Positive:** Idempotent ingestion simplifies worker retries.
- **Negative:** Rebuilds cost time/compute for large corpora (acceptable for MVP scale).
- **Negative:** Requires discipline to keep deletions synchronized across both stores (covered by tests in later phases).
