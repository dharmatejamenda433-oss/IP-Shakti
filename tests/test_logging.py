"""Tests for ipsakti.core.logging structured JSON formatter and redaction."""

from __future__ import annotations

import json
import logging

from ipsakti.core.logging import JsonLogFormatter, configure_logging, get_logger
from ipsakti.core.request_context import clear_request_context, request_context


def _format(record: logging.LogRecord) -> dict[str, object]:
    payload: dict[str, object] = json.loads(JsonLogFormatter().format(record))
    return payload


def test_formatter_emits_json_with_core_fields() -> None:
    clear_request_context()
    record = logging.LogRecord(
        name="ipsakti.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    payload = _format(record)
    assert payload["level"] == "INFO"
    assert payload["logger"] == "ipsakti.test"
    assert payload["message"] == "hello world"
    assert "timestamp" in payload


def test_formatter_includes_request_context() -> None:
    clear_request_context()
    with request_context(request_id="r-1", user_id="u-1", tenant_id="t-1"):
        record = logging.LogRecord(
            name="ipsakti.test",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="ctx",
            args=(),
            exc_info=None,
        )
        payload = _format(record)
    assert payload["request_id"] == "r-1"
    assert payload["user_id"] == "u-1"
    assert payload["tenant_id"] == "t-1"


def test_formatter_redacts_sensitive_extras() -> None:
    clear_request_context()
    record = logging.LogRecord(
        name="ipsakti.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="login",
        args=(),
        exc_info=None,
    )
    record.password = "hunter2"  # noqa: S105 - test value
    record.access_token = "abc.def.ghi"
    record.safe_field = "visible"
    payload = _format(record)
    assert payload["password"] == "***REDACTED***"
    assert payload["access_token"] == "***REDACTED***"
    assert "hunter2" not in json.dumps(payload)
    assert payload["safe_field"] == "visible"


def test_configure_logging_is_idempotent() -> None:
    configure_logging("INFO")
    first = len(logging.getLogger().handlers)
    configure_logging("INFO")
    second = len(logging.getLogger().handlers)
    assert first == second == 1


def test_get_logger_returns_named_logger() -> None:
    assert get_logger("ipsakti.x").name == "ipsakti.x"
