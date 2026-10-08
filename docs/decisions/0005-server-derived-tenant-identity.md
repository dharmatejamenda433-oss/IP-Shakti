# ADR 0005 — Server-derived tenant identity + query-time isolation

**Status:** Accepted

## Context
IP-SAKTI is multi-tenant. Tenant A must never access Tenant B's documents, chunks, search results,
citations, metadata, or audit records. A common failure mode is trusting a client-supplied
`tenant_id`, or fetching all tenants' data and filtering in application code (which leaks via IDOR,
caching, or bugs).

## Decision
- **Tenant identity is derived server-side** from the authenticated principal (token → user → tenant membership). Client-supplied `tenant_id` is never trusted for authorization.
- **Isolation is enforced at query time**, in both stores:
  - PostgreSQL: every tenant-scoped query filters by the resolved `tenant_id`.
  - Qdrant: tenant filter is part of the search request, never applied after retrieval.
  - BM25: index scope is tenant-bounded.
- **Authorization** checks identity → tenant → role → permission → resource ownership on every protected route.
- **Safe failure:** direct ID manipulation (accessing another tenant's resource by ID) returns a uniform not-found/forbidden response with no cross-tenant data and no existence oracle.

## Consequences
- **Positive:** Isolation is structural, not incidental; testable via IDOR/tenant-isolation security tests.
- **Positive:** No retrieve-all-then-filter performance or leakage risk.
- **Negative:** Every data-access path must thread the resolved tenant through — enforced by shared dependencies and reviewed in Phase 4.
