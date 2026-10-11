"""Request-context middleware.

Assigns each request a correlation id (honouring an inbound ``X-Request-ID`` when
present), binds it to the context vars used by structured logging, and echoes it on
the response. Deeper identity context (user_id/tenant_id) is added by the auth
dependency once the principal is resolved.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from ipsakti.core.request_context import new_request_id, request_context


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a per-request correlation id for the duration of the request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Populate request context, call downstream, and tag the response."""
        request_id = request.headers.get("X-Request-ID") or new_request_id()
        with request_context(request_id=request_id):
            response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
