# ADR 0008 — Secure, atomic, immutable document storage with UUID paths

**Status:** Accepted

## Context
Phase 5 accepts PDF uploads from authenticated tenants and must persist the bytes
before an asynchronous worker extracts and indexes them (FR-ING-1/2, spec §9). The
requirements are explicit that storage must be **path-traversal-safe** (NFP-SEC),
that files are validated for **type, MIME, magic bytes, and size** before being
stored (FR-ING-2), and that SHA-256 supports both **integrity** and **duplicate
detection**. The stack forbids S3/object storage for the MVP (spec §4: "No S3 for
MVP — local filesystem only"), and source PDFs must never be committed to Git.

Client-supplied filenames and content types are attacker-controlled and cannot be
trusted. A naive design that stores an upload under its original name, or that
writes in place, would be vulnerable to traversal, partial/corrupt files, and
spoofed types.

## Decision
1. **UUID storage keys, no client input in paths.** A version's relative path is
   `{tenant_hex}/{document_hex}/v{n}.pdf`, built only from server-generated UUIDs
   and an integer. The original filename is never used to construct a path (it is
   validated for a `.pdf` extension only, and otherwise discarded), so a
   traversal-laden name is inert.
2. **Containment is enforced at resolve time.** Every relative key is resolved and
   re-checked to live inside the configured storage root before any write
   (`resolve_within_root`); a path that escapes raises a validation error.
3. **Validate before trusting.** Declared MIME type is normalized and allow-listed,
   the filename extension is checked, and — authoritatively — the leading `%PDF-`
   magic bytes are verified from the stream itself. Size is enforced *during*
   streaming against `IPSAKTI_MAX_UPLOAD_BYTES`, so an oversized upload is
   rejected without ever being fully buffered or written.
4. **Atomic write, then immutable.** Bytes stream to a sibling `*.part` temp file,
   are `fsync`-ed, and moved into place with `os.replace` (atomic on POSIX and
   Windows). A committed file is never rewritten; new content is a new version
   path. Any failure before commit removes the temp file, so partial files never
   leak.
5. **SHA-256 in a single pass.** The digest is computed while streaming and stored
   on the version row. Duplicate detection is **per tenant**: identical content
   re-uploaded within a tenant is rejected with a 409, while the same content in a
   different tenant is allowed (tenants are isolated; hashes are not shared).
6. **Ordering avoids orphans.** The file is committed only after the duplicate
   check passes, and the DB rows are inserted before the request transaction
   commits; if row creation fails, the committed file is removed. Postgres remains
   the system of record and the stored path is recorded on the version (ADR 0001).

## Consequences
- **Positive:** Traversal is structurally impossible (no user input reaches a
  path) and defended in depth (resolve-time containment check). Spoofed MIME/
  extension cannot pass the magic-byte check. Readers never observe a partial file
  because writes are atomic.
- **Positive:** Duplicate detection is cheap (indexed `file_sha256`) and scoped to
  the tenant, preserving isolation.
- **Negative:** Content-addressed dedup is *not* applied across tenants, so the same
  PDF stored by two tenants occupies two files. Accepted: cross-tenant dedup would
  leak the existence of content between isolation boundaries.
- **Negative:** Local filesystem storage does not scale horizontally and offers no
  built-in replication. Accepted for the MVP per spec §4; the storage module is
  isolated behind `stage/commit/remove` helpers, so a future object-store backend
  is a localized swap.
- **Operational:** `data/storage` is gitignored and volume-mounted in deployment
  (Phase 23/24); backups cover Postgres and this directory together so version
  rows and their files stay consistent.
