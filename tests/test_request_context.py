"""Tests for ipsakti.core.request_context."""

from __future__ import annotations

from ipsakti.core.request_context import (
    clear_request_context,
    get_request_id,
    get_tenant_id,
    get_user_id,
    new_request_id,
    request_context,
    set_request_context,
)


def test_context_unset_by_default() -> None:
    clear_request_context()
    assert get_request_id() is None
    assert get_user_id() is None
    assert get_tenant_id() is None


def test_request_context_manager_binds_and_restores() -> None:
    clear_request_context()
    with request_context(request_id="req-1", user_id="user-1", tenant_id="tenant-1") as rid:
        assert rid == "req-1"
        assert get_request_id() == "req-1"
        assert get_user_id() == "user-1"
        assert get_tenant_id() == "tenant-1"
    # Restored to unset on exit.
    assert get_request_id() is None
    assert get_user_id() is None
    assert get_tenant_id() is None


def test_request_context_generates_id_when_absent() -> None:
    clear_request_context()
    with request_context() as rid:
        assert rid
        assert get_request_id() == rid


def test_set_request_context_partial_update() -> None:
    clear_request_context()
    set_request_context(user_id="u-9")
    assert get_user_id() == "u-9"
    assert get_request_id() is None


def test_new_request_id_is_unique() -> None:
    assert new_request_id() != new_request_id()
