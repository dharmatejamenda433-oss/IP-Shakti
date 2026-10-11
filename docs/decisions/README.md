# Architecture Decision Records

Lightweight ADRs documenting the significant, hard-to-reverse decisions for IP-SAKTI.
Format: **Context → Decision → Consequences**. Status is one of Accepted / Superseded / Proposed.

| ADR | Title | Status |
| --- | --- | --- |
| [0001](0001-postgres-system-of-record-qdrant-derived-index.md) | PostgreSQL as system of record, Qdrant as derived index | Accepted |
| [0002](0002-plain-python-worker.md) | Plain polling Python worker (no Celery/Redis) | Accepted |
| [0003](0003-explicit-hybrid-retrieval.md) | Explicit hybrid retrieval + RRF (no framework) | Accepted |
| [0004](0004-provider-isolated-generation.md) | Provider-isolated generation, evidence-only + abstention | Accepted |
| [0005](0005-server-derived-tenant-identity.md) | Server-derived tenant identity + query-time isolation | Accepted |
| [0006](0006-backend-citation-validation.md) | Conservative backend citation validation | Accepted |
| [0007](0007-stateless-jwt-with-refresh-denylist.md) | Stateless JWT sessions with an in-process refresh-token denylist | Accepted |
