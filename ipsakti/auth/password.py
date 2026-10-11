"""Password hashing and verification.

Uses bcrypt via passlib. ``truncate_error=True`` makes over-length passwords fail
loudly instead of being silently truncated at bcrypt's 72-byte limit, so callers
cannot be surprised by two distinct passwords hashing identically. The API schema
enforces the same bound at the boundary.
"""

from __future__ import annotations

from passlib.context import CryptContext

# bcrypt rejects (rather than truncates) passwords whose UTF-8 length exceeds the
# scheme's block size; the schema mirrors this bound.
BCRYPT_MAX_BYTES = 72

_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__truncate_error=True)

# A pre-computed hash used to equalize timing when the supplied email is unknown,
# so login does not leak whether an account exists (see service.authenticate).
_DUMMY_HASH = _context.hash("ipsakti-timing-equalizer-password")


class PasswordTooLongError(ValueError):
    """Raised when a password exceeds bcrypt's supported length."""


def hash_password(plain: str) -> str:
    """Return a salted bcrypt hash of ``plain``.

    Raises:
        PasswordTooLongError: If the UTF-8 encoding exceeds :data:`BCRYPT_MAX_BYTES`.
    """
    if len(plain.encode("utf-8")) > BCRYPT_MAX_BYTES:
        msg = f"password must not exceed {BCRYPT_MAX_BYTES} bytes"
        raise PasswordTooLongError(msg)
    result: str = _context.hash(plain)
    return result


def verify_password(plain: str, hashed: str) -> bool:
    """Return True when ``plain`` matches ``hashed``.

    Never raises for malformed input or over-length passwords; both are treated as
    a non-match so authentication failures stay uniform.
    """
    try:
        result: bool = _context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False
    return result


def verify_password_dummy(plain: str) -> None:
    """Burn comparable CPU time against a fixed hash (timing equalization)."""
    try:
        _context.verify(plain, _DUMMY_HASH)
    except (ValueError, TypeError):
        pass


def needs_rehash(hashed: str) -> bool:
    """Return True when ``hashed`` should be recomputed under current parameters."""
    try:
        return bool(_context.needs_update(hashed))
    except (ValueError, TypeError):
        return True
