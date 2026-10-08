"""Per-request context propagated across the call stack.

Holds correlation identifiers (request_id, user_id, tenant_id) in context vars so
structured logging and audit can attach them without threading arguments through
every function. Values are isolated per asyncio task / thread.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_tenant_id: ContextVar[str | None] = ContextVar("tenant_id", default=None)


def new_request_id() -> str:
    """Generate a fresh request identifier."""
    return uuid4().hex


def get_request_id() -> str | None:
    """Return the current request_id, if any."""
    return _request_id.get()


def get_user_id() -> str | None:
    """Return the current authenticated user_id, if any."""
    return _user_id.get()


def get_tenant_id() -> str | None:
    """Return the current tenant_id, if any."""
    return _tenant_id.get()


def set_request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> None:
    """Set any subset of the request context values."""
    if request_id is not None:
        _request_id.set(request_id)
    if user_id is not None:
        _user_id.set(user_id)
    if tenant_id is not None:
        _tenant_id.set(tenant_id)


def clear_request_context() -> None:
    """Reset all request context values to unset."""
    _request_id.set(None)
    _user_id.set(None)
    _tenant_id.set(None)


@contextmanager
def request_context(
    *,
    request_id: str | None = None,
    user_id: str | None = None,
    tenant_id: str | None = None,
) -> Iterator[str]:
    """Bind request context for the duration of a block.

    Yields the effective request_id (generating one if not supplied) and restores
    the previous context on exit.
    """
    tokens = [
        (_request_id, _request_id.set(request_id or new_request_id())),
        (_user_id, _user_id.set(user_id)),
        (_tenant_id, _tenant_id.set(tenant_id)),
    ]
    try:
        yield _request_id.get() or ""
    finally:
        for var, token in tokens:
            var.reset(token)
