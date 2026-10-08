# ADR 0004 — Provider-isolated generation, evidence-only + abstention

**Status:** Accepted

## Context
The LLM is a swappable external dependency (Groq today). The rest of the application must not couple
to Groq's SDK, model names, or response shapes. Answers must be grounded strictly in retrieved
evidence, and the system must be able to refuse when evidence is insufficient.

## Decision
Isolate generation behind a small interface in `ipsakti/generation/`:

```
generation/
  provider.py         # GenerationProvider protocol (generate / stream)
  groq_provider.py    # the only module that knows about Groq
  prompts.py          # evidence-only system/instruction prompts
  schemas.py          # request/response types used across the app
```

Rules:
- Only `groq_provider.py` imports Groq; the app depends on `provider.py` and `schemas.py`.
- Model name is configurable; API key comes from environment variables — never committed.
- The prompt instructs the model to: answer only from supplied evidence, not invent facts or citations, distinguish evidence from inference, abstain when evidence is insufficient, cite supplied sources, and avoid outside knowledge.
- Groq is engaged **only after** retrieval is reliable; if the relevance gate fails, no LLM call is made.

## Consequences
- **Positive:** Provider can be swapped/tested with a fake; prompts and grounding rules are centralized.
- **Positive:** Keeps the "no LangChain" boundary clean — a thin protocol replaces a framework.
- **Negative:** We own the streaming/error-handling code (also required for SSE in Phase 19).
