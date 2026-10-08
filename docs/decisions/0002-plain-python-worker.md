# ADR 0002 — Plain polling Python worker (no Celery/Redis)

**Status:** Accepted

## Context
Document ingestion is a long-running, multi-stage job (extract → chunk → embed → index). It must run
outside the request path so uploads return quickly. The spec explicitly prohibits Celery, Redis, and
Kafka, and forbids introducing brokers/orchestration merely for abstraction.

## Decision
Use a **single plain Python worker** started with `python -m ipsakti.worker`. It polls the
`ingestion_jobs` table in PostgreSQL, atomically claims a job (UPLOADED → PROCESSING), runs the
pipeline, and updates state (EXTRACTED → CHUNKED → INDEXING → COMPLETED / FAILED) with
`attempt_count`, `error_message`, `started_at`, `completed_at`, `updated_at`.

Properties:
- **Idempotent:** deterministic chunk/point IDs mean re-processing upserts rather than duplicates.
- **Retryable:** FAILED jobs can be re-claimed up to a configured attempt limit.
- **Claim safety:** job claiming uses a transactional update so concurrent workers cannot double-claim.

## Consequences
- **Positive:** Zero extra infrastructure; simple to run, test, and reason about; aligns with the "no unnecessary brokers" rule.
- **Positive:** PostgreSQL is already the system of record (ADR 0001), so the queue needs no new store.
- **Negative:** Polling has latency and is less scalable than a dedicated broker — acceptable at MVP scale.
- **Negative:** Horizontal scaling requires careful claim semantics (handled via transactional claiming).
