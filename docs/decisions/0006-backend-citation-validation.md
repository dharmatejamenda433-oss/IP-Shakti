# ADR 0006 — Conservative backend citation validation

**Status:** Accepted

## Context
The system's promise is citation-grounded answers. LLMs cannot be trusted to produce or preserve
citation metadata faithfully — they may invent, drop, or misnumber citations. At the same time, we
must not overclaim: a citation attached to a sentence is not automatic proof that the sentence is
semantically supported by that source.

## Decision
Citations are **validated on the backend**, not trusted from the model. For each citation the backend
verifies:

1. The citation **exists** in the retrieved context set.
2. It **belongs to the retrieved context** actually supplied to the model (no out-of-band sources).
3. It **belongs to the authorized tenant**.
4. It points to the **correct document version**.
5. It carries **valid page/source metadata**.

The Context Builder maintains the authoritative map `citation_id → chunk_id → document_version →
document → page`, and only citations resolvable through this map are emitted. Validation is
**conservative**: unresolved or mismatched citations are rejected rather than passed through.

We explicitly **do not claim perfect automated semantic grounding verification.** Groundedness is
assessed with deterministic checks plus curated human review (Phase 29 of the spec / Phase 26 eval).

## Consequences
- **Positive:** Fabricated or misattributed citations are filtered before reaching the user; provenance is verifiable end-to-end.
- **Positive:** Honest about limits — no false "verified grounding" claims.
- **Negative:** Semantic entailment between claim and source is not fully machine-checked; mitigated by human review on a curated subset.
