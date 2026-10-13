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

### PDF extraction (Phase 6)

`ipsakti.ingestion.extract_pdf(path, *, password=None, max_pages=None)` returns a page-aware
`ExtractionResult`: per-page text (1-based page numbers, every page recorded — blanks included),
structural blocks (`HEADING` / `PARAGRAPH` / `TABLE`) with resolved `section` / `subsection`
context, and total character count. It is a library used by the ingestion worker (Phase 10); no
HTTP endpoint is added yet.

Failures are explicit, never silent (each raises `ExtractionError` with a distinct `code`):
`corrupt_document`, `password_required`, `ocr_required` (scanned/image-only), `empty_document`,
and `too_large` (over `max_pages`). This wires into the state machine's `FAILED` path later.

### Running the API

```bash
# Apply migrations (requires IPSAKTI_DATABASE_URL in .env), then start the server:
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn ipsakti.api.app:create_app --factory --reload
```

Endpoints implemented so far (under `/api/v1`): `POST /auth/login`, `POST /auth/refresh`,
`POST /auth/logout`, `GET /users/me`, `POST /documents` (multipart PDF upload),
`GET /documents/{id}`, plus `GET /health`. Interactive docs at `/docs`.

`POST /documents` requires the `document:upload` permission (ADMIN/MANAGER) and validates the
upload before storing it: MIME type, `.pdf` extension, `%PDF-` magic bytes, and size
(`IPSAKTI_MAX_UPLOAD_BYTES`). Files are stored under `data/storage` at a server-generated UUID
path via an atomic write, hashed with SHA-256, and rejected as a 409 if identical content already
exists in the tenant. Each upload creates a `Document`, a current `DocumentVersion`, and an
`IngestionJob` in the `UPLOADED` state — extraction/indexing is handled by the worker (Phase 10).

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -F "file=@/path/to/doc.pdf;type=application/pdf" \
  -F "title=My Document" -F "document_type=ACT" -F "domain=AYURVEDA"
```

RBAC roles/permissions must be seeded once per database via `ipsakti.auth.bootstrap(session)`;
the built-in role templates (ADMIN/MANAGER/USER) are global and shared across tenants.
Provisioning tenants/users is an admin operation delivered in a later phase — tests create them
directly. See [`docs/decisions/0007`](docs/decisions/0007-stateless-jwt-with-refresh-denylist.md)
for the token/revocation design and
[`docs/decisions/0008`](docs/decisions/0008-secure-atomic-document-storage.md) for storage.

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
