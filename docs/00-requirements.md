# IP-SAKTI — Requirements

Phase 0 deliverable. Captures *what* the system must do and *how well*, without prescribing
implementation (see [`01-architecture.md`](01-architecture.md) for that).

---

## 1. Problem context

SIH problem statement **SIH26045** asks for an AI knowledge and decision-support platform over
Ayurveda / traditional-knowledge / IP / regulatory material. The differentiator is **trust**:
answers must be grounded in authoritative sources, carry verifiable citations, and respect
strict multi-tenant access boundaries.

The corpus spans:

- Indian IP law (Patents Act 1970, Patents Rules 2003, AYUSH examination guidelines)
- AYUSH / Ayurveda regulatory material
- Drug regulations (Drugs & Cosmetics Act 1940, Rules 1945)
- Biodiversity / access-and-benefit-sharing (Biological Diversity Act 2002)
- Relevant international material (WIPO, CBD, treaties)
- Relevant case law
- Structured registry information where appropriate

---

## 2. Functional requirements

### 2.1 Ingestion
- **FR-ING-1** Accept PDF uploads through an authenticated, authorized API.
- **FR-ING-2** Validate file type, MIME, magic-byte signature, and size before storing.
- **FR-ING-3** Extract text preserving document, page number, section, subsection, and headings where detectable; extract tables where reasonably possible.
- **FR-ING-4** Never silently discard pages. Handle empty, corrupt, password-protected, image-only, very large, and malformed PDFs explicitly.
- **FR-ING-5** If a document requires OCR, report that clearly rather than pretending extraction succeeded.
- **FR-ING-6** Chunk text using structure-aware recursive splitting (~500–700 tokens, ~50–100 token overlap — configurable).
- **FR-ING-7** Assign deterministic chunk IDs; embedding + indexing must be idempotent.
- **FR-ING-8** Track ingestion state: UPLOADED → PROCESSING → EXTRACTED → CHUNKED → INDEXING → COMPLETED / FAILED, with attempt_count, error_message, and timestamps.

### 2.2 Retrieval
- **FR-RET-1** Support dense retrieval over Qdrant with cosine similarity.
- **FR-RET-2** Support BM25 lexical retrieval (exact terms, section refs, drug/formulation names, patent terminology).
- **FR-RET-3** Fuse results with Reciprocal Rank Fusion (configurable `k`), deduplicated by chunk_id.
- **FR-RET-4** Rerank hybrid candidates with a cross-encoder (candidate pool 20–30, final 5–8 — configurable).
- **FR-RET-5** Apply a relevance gate; return a controlled insufficient-evidence result when evidence is weak. Never let the LLM guess.
- **FR-RET-6** Enforce tenant authorization filters *during* retrieval, never retrieve-all-then-filter.

### 2.3 Generation
- **FR-GEN-1** Answer only from supplied evidence; abstain when evidence is insufficient.
- **FR-GEN-2** Instruct the model to not invent facts or citations, distinguish evidence from inference, and avoid outside knowledge.
- **FR-GEN-3** Stream chat responses via SSE (events: status, token, citation, error, done).
- **FR-GEN-4** Isolate the LLM provider behind an interface; the app must not depend on Groq internals.

### 2.4 Citations & provenance
- **FR-CIT-1** Backend validates every citation: exists, belongs to retrieved context, belongs to authorized tenant, points to correct document version, has valid page/source metadata.
- **FR-CIT-2** Preserve and expose full trace: Answer → Citation → Chunk → Document Version → Source.
- **FR-CIT-3** Store source provenance per document: title, source, authority, document_type, domain, jurisdiction, country, language, publication_date, effective_date, version, status, source_url.
- **FR-CIT-4** Do not claim perfect automated semantic grounding; use conservative validation.

### 2.5 Identity, tenancy, authorization
- **FR-AUTH-1** Secure password hashing; login; short-lived access token; refresh token; logout/revocation.
- **FR-AUTH-2** Derive tenant identity server-side from authenticated identity. Never trust client-supplied tenant_id.
- **FR-AUTH-3** RBAC with roles ADMIN / MANAGER / USER and permissions document:upload, document:read, document:delete, search:execute, user:manage, audit:read.
- **FR-AUTH-4** Authorization checks identity + tenant + role + permission + resource ownership.
- **FR-TEN-1** Hard tenant isolation: Tenant A can never access Tenant B resources (retrieval, download, deletion, search, chat, citations, metadata, audit). Direct ID manipulation must fail safely.

### 2.6 Document versioning
- **FR-VER-1** Every indexed chunk belongs to a document version; never mix versions accidentally.
- **FR-VER-2** On reindex, old vectors remain distinguishable; retrieval respects configured version semantics.
- **FR-VER-3** Deletion must not leave orphaned searchable vectors; keep PostgreSQL/Qdrant consistent.

### 2.7 Audit & observability
- **FR-AUD-1** Audit LOGIN, DOCUMENT_UPLOAD, DOCUMENT_DELETE, SEARCH, CHAT, USER_CHANGE with user_id, tenant_id, action, resource, timestamp, request_id, result.
- **FR-OBS-1** Structured logging with request_id, user_id, tenant_id, endpoint, status, and per-stage latency (retrieval, embedding, BM25, reranking, LLM, total).

### 2.8 Evaluation
- **FR-EVAL-1** Gold dataset of 50–100 questions (query, expected doc/chunk, domain, jurisdiction, optional difficulty).
- **FR-EVAL-2** Report Recall@5, Recall@10, MRR for BM25, Dense, Hybrid, Hybrid+reranker — from actual runs only, never fabricated.
- **FR-EVAL-3** Generation evaluation: citation validity, insufficient-evidence behavior, groundedness, completeness, unsupported claims — deterministic checks plus curated human review.

---

## 3. Non-functional requirements

- **NFP-SEC** No hard-coded secrets; credentials from environment. Path-traversal-safe storage. No secrets/credentials/raw sensitive content in logs.
- **NFP-TYPE** Typed, explicit, testable code; type hints where practical.
- **NFP-SIMP** Prefer simple, modular, maintainable code. No over-abstraction, premature optimization, or distributed infrastructure.
- **NFP-PERF** Measure latency at each pipeline stage; no unmeasured performance claims.
- **NFP-RELI** Worker is idempotent; ingestion failures are retryable and observable.
- **NFP-DEPLOY** Docker Compose deployment with HTTPS, persistent volumes, health checks, restart policies, DB backup strategy, Qdrant persistence. No Kubernetes.

---

## 4. Explicit scope exclusions

- Not a generic chatbot.
- No automatic download of copyrighted/restricted documents.
- No scraping of TKDL and no attempt to obtain the private TKDL database.
- Source PDFs are never committed to Git.
- No chat persistence tables until chat persistence is actually required.
- No S3 for MVP (local filesystem only).
- No OCR unless the actual corpus demonstrably requires it.
- No ML metadata classifier unless a concrete need is demonstrated — prefer deterministic metadata and explicit filters.

---

## 5. Initial authoritative corpus

| # | Document | Domain | Jurisdiction |
| --- | --- | --- | --- |
| 1 | Guidelines for Examination of Ayush Related Inventions – 2025 | patents / ayush | India |
| 2 | The Patents Act, 1970 | patents | India |
| 3 | The Patents Rules, 2003 | patents | India |
| 4 | Drugs and Cosmetics Act, 1940 | drugs | India |
| 5 | Drugs and Cosmetics Rules, 1945 | drugs | India |
| 6 | Biological Diversity Act, 2002 | biodiversity | India |

Additional API/AFI material only from legally available official sources.

Suggested local layout under `data/corpus/` (never committed):
`india/{patents,ayush,drugs,biodiversity,ayurveda,case_law}`, `international/{treaties,wipo,cbd}`.
