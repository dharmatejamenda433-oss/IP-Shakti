"""In-process refresh-token revocation denylist.

Logout and refresh rotation revoke a refresh token's ``jti`` so it can no longer be
exchanged for new tokens. Access tokens are stateless and short-lived; they are not
denylisted and simply expire.

Scope note (see ADR 0007): this is a single-process, in-memory store. It does not
survive a restart and is not shared across processes. When the deployment scales
beyond one API process, replace it with a persisted ``revoked_tokens`` table or a
per-user ``token_version``. The ``consume_once`` operation makes refresh rotation
atomic only within this process.
"""

from __future__ import annotations

import threading
import time


class TokenDenylist:
    """A thread-safe set of revoked JTIs with automatic expiry-based eviction."""

    def __init__(self) -> None:
        """Initialize an empty, lock-guarded expiry map."""
        self._expiries: dict[str, float] = {}
        self._lock = threading.Lock()

    def revoke(self, jti: str, *, expires_at_epoch: float) -> None:
        """Record ``jti`` as revoked until ``expires_at_epoch`` (unix seconds).

        Entries are pruned once their underlying token would have expired anyway,
        so the store cannot grow without bound.
        """
        now = time.time()
        with self._lock:
            self._prune(now)
            if expires_at_epoch > now:
                self._expiries[jti] = expires_at_epoch

    def consume_once(self, jti: str, *, expires_at_epoch: float) -> bool:
        """Atomically mark a token used, returning False if it was already used.

        This closes the check-then-revoke race for concurrent refresh requests
        handled by this process. It does not coordinate across multiple workers.
        """
        now = time.time()
        with self._lock:
            self._prune(now)
            if jti in self._expiries or expires_at_epoch <= now:
                return False
            self._expiries[jti] = expires_at_epoch
            return True

    def is_revoked(self, jti: str) -> bool:
        """Return True when ``jti`` is currently revoked."""
        now = time.time()
        with self._lock:
            self._prune(now)
            return jti in self._expiries

    def _prune(self, now: float) -> None:
        expired = [jti for jti, exp in self._expiries.items() if exp <= now]
        for jti in expired:
            del self._expiries[jti]

    def clear(self) -> None:
        """Remove all entries (used by tests)."""
        with self._lock:
            self._expiries.clear()


# Process-wide singleton used by the auth service and API dependencies.
denylist = TokenDenylist()
