"""Translation of domain errors into consistent JSON HTTP responses.

Every :class:`~ipsakti.core.errors.IPSaktiError` becomes a body of the shape
``{"error": {"code": ..., "message": ...}}`` with the exception's status code, so
clients get a stable machine-readable contract without internal details leaking.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from ipsakti.core.errors import IPSaktiError


def _error_response(exc: IPSaktiError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
        headers=headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    """Attach the domain-error exception handler to ``app``."""

    @app.exception_handler(IPSaktiError)
    async def _handle_ipsakti_error(request: Request, exc: IPSaktiError) -> JSONResponse:
        return _error_response(exc)
