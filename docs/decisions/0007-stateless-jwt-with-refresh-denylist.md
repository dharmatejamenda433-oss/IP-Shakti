# ADR 0007 — Stateless JWT sessions with an in-process refresh-token denylist

**Status:** Accepted

## Context
Phase 4 needs login, short-lived access tokens, refresh tokens, and logout/revocation
(spec §22). The stack forbids Redis and a message broker (spec §5), and the initial
table list (spec §21) deliberately excludes any session/token table — "do not create
tables until actually required." We still must not trust client-supplied tenant
identity (spec §22/§24, ADR 0005).

The tension: JWTs are stateless, but *revocation* is inherently stateful. We need the
simplest design that gives real logout without pulling in infrastructure the spec
bans or a schema the spec defers.

## Decision
1. **Access tokens are stateless HS256 JWTs**, short-lived (default 15 min), signed
   with `IPSAKTI_SECRET_KEY` from the environment. Claims: `sub` (user id), `tid`
   (tenant id), `typ`, `jti`, `iat`, `exp`, `iss`. The `typ` claim is enforced on
   decode so an access token can never be replayed as a refresh token.
2. **Refresh tokens** are longer-lived (default 7 days) and **rotating**: each
   successful `/auth/refresh` revokes the presented `jti` and issues a new pair, so a
   stolen refresh token is single-use.
3. **Revocation uses an in-process, in-memory JTI denylist** with automatic
   expiry-based eviction (entries are dropped once the underlying token would have
   expired anyway, so the store is bounded). Only refresh tokens are denylisted;
   access tokens simply expire.
4. **Identity is revalidated against the database on every request.** The `tid`/`sub`
   in a token are treated as a lookup key, never as proof of current eligibility: a
   disabled user or suspended tenant invalidates already-issued tokens immediately,
   and the effective tenant is always taken from the persisted user (ADR 0005).
5. **Login failure modes are uniform** (unknown email, wrong password, disabled
   account, suspended tenant all return the same generic 401) with timing
   equalization on unknown emails, to prevent account enumeration.

## Consequences
- **Positive:** No new infrastructure (no Redis) and no new table — consistent with
  spec §5 and §21. Logout and refresh rotation are real, not cosmetic.
- **Positive:** Per-request DB revalidation means revocation-by-status is instant and
  the stateless access token cannot outlive a disabled account's eligibility check.
- **Negative:** The denylist is **per-process and not durable**. It does not survive a
  restart, and with multiple API workers a refresh token revoked on one worker is not
  yet revoked on another. Accepted for the current single-process MVP.
- **Migration path:** When the deployment scales beyond one API process, replace the
  `TokenDenylist` with a persisted `revoked_tokens` table or a per-user
  `token_version` column. Call sites depend only on `revoke`/`is_revoked`, so the swap
  is localized and requires no change to the API contract.
