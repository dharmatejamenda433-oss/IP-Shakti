# ADR 0003 — Explicit hybrid retrieval + RRF (no framework)

**Status:** Accepted

## Context
Retrieval quality is the product's core differentiator. We need dense (semantic) and BM25 (lexical)
retrieval combined, and the combination must be transparent, testable, and tunable. Frameworks like
LangChain would hide this logic, and the spec prohibits them and requires RRF to be implemented and
tested explicitly.

## Decision
Implement retrieval as explicit, independently testable stages:

1. **Dense** — embed the query (bge-small-en-v1.5), search Qdrant with tenant authorization filters applied *in the query*.
2. **BM25** — `rank-bm25` over a tenant-scoped in-process index for exact terms, section refs, drug/formulation names, patent terminology.
3. **Deduplicate** candidates by `chunk_id`.
4. **Reciprocal Rank Fusion** — `RRF(d) = Σ 1 / (k + rank)` with `k` configurable, implemented directly in Python.
5. **Cross-encoder rerank** — `bge-reranker-base` over the fused pool (20–30 candidates → 5–8 final), batched, oversized text handled safely.
6. **Relevance gate** — configurable threshold; below it, return a controlled insufficient-evidence result instead of calling the LLM.

All tunables (k, pool size, final count, threshold) come from configuration.

## Consequences
- **Positive:** Every stage is unit-testable (RRF and BM25 especially); behavior is defensible in review/interviews.
- **Positive:** Easy to benchmark each strategy separately (required for Phase 15 evaluation).
- **Negative:** More hand-written code than a framework call — intentional, and bounded.
- **Negative:** In-process BM25 index must be kept in sync with the corpus (rebuild/update logic required).
