from __future__ import annotations

import time

from ipsakti.auth.revocation import TokenDenylist


def test_revoke_and_check() -> None:
    dl = TokenDenylist()
    dl.revoke("jti-1", expires_at_epoch=time.time() + 60)
    assert dl.is_revoked("jti-1") is True
    assert dl.is_revoked("jti-2") is False


def test_expired_entries_are_pruned() -> None:
    dl = TokenDenylist()
    dl.revoke("old", expires_at_epoch=time.time() - 1)
    # Already-expired tokens are not stored (they can never be replayed).
    assert dl.is_revoked("old") is False


def test_entry_evicted_after_expiry() -> None:
    dl = TokenDenylist()
    dl.revoke("short", expires_at_epoch=time.time() + 0.01)
    assert dl.is_revoked("short") is True
    time.sleep(0.02)
    assert dl.is_revoked("short") is False


def test_clear() -> None:
    dl = TokenDenylist()
    dl.revoke("jti", expires_at_epoch=time.time() + 60)
    dl.clear()
    assert dl.is_revoked("jti") is False
