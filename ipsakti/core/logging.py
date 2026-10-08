"""Structured logging.

Emits single-line JSON logs enriched with the current request context
(request_id, user_id, tenant_id). No external observability platform is used —
this is stdlib `logging` with a JSON formatter, per the spec.

Sensitive values are never logged: the formatter redacts a fixed set of keys and
callers must not pass secrets or raw credentials as extras.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime
from typing import Any

from ipsakti.core.request_context import get_request_id, get_tenant_id, get_user_id

# Keys that must never appear in log output, even if passed accidentally.
_REDACTED_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "secret_key",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "api_key",
        "groq_api_key",
        "credential",
        "credentials",
    }
)
_REDACTED_VALUE = "***REDACTED***"

# Standard LogRecord attributes that are not user-supplied extras.
_RESERVED_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "module",
        "msecs",
        "message",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonLogFormatter(logging.Formatter):
    """Format log records as single-line JSON objects with request context."""

    def format(self, record: logging.LogRecord) -> str:
        """Render `record` as a JSON line, redacting sensitive keys."""
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        request_id = get_request_id()
        user_id = get_user_id()
        tenant_id = get_tenant_id()
        if request_id is not None:
            payload["request_id"] = request_id
        if user_id is not None:
            payload["user_id"] = user_id
        if tenant_id is not None:
            payload["tenant_id"] = tenant_id

        for key, value in record.__dict__.items():
            if key in _RESERVED_ATTRS or key.startswith("_"):
                continue
            payload[key] = _REDACTED_VALUE if key.lower() in _REDACTED_KEYS else value

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)

        return json.dumps(payload, default=str, ensure_ascii=True)


def configure_logging(level: str = "INFO") -> None:
    """Configure root logging with the JSON formatter.

    Safe to call multiple times: existing handlers on the root logger are cleared
    first so log lines are not duplicated.
    """
    root = logging.getLogger()
    root.setLevel(level.upper())
    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream = logging.StreamHandler(stream=sys.stdout)
    stream.setFormatter(JsonLogFormatter())
    root.addHandler(stream)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger for a module."""
    return logging.getLogger(name)
