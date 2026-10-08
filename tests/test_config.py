"""Tests for ipsakti.core.config.Settings."""

from __future__ import annotations

from typing import Any

import pytest
from ipsakti.core.config import Settings
from pydantic import ValidationError as PydanticValidationError


def _settings(**overrides: Any) -> Settings:
    """Build Settings from explicit kwargs, ignoring any ambient .env file."""
    return Settings(_env_file=None, **overrides)


def test_defaults_are_applied() -> None:
    s = _settings()
    assert s.env == "development"
    assert s.api_v1_prefix == "/api/v1"
    assert s.embedding_dim == 384
    assert s.qdrant_collection == "ipsakti_chunks"
    assert s.rrf_k == 60


def test_secret_key_is_not_plain_str() -> None:
    s = _settings(secret_key="super-secret-value")
    # SecretStr must not leak the raw value via str()/repr().
    assert "super-secret-value" not in str(s.secret_key)
    assert s.secret_key.get_secret_value() == "super-secret-value"


def test_log_level_normalized_to_upper() -> None:
    s = _settings(log_level="debug")
    assert s.log_level == "DEBUG"


def test_invalid_log_level_rejected() -> None:
    with pytest.raises(PydanticValidationError):
        _settings(log_level="VERBOSE")


def test_chunk_overlap_must_be_smaller_than_target() -> None:
    with pytest.raises(PydanticValidationError):
        _settings(chunk_target_tokens=100, chunk_overlap_tokens=100)


def test_relevance_threshold_bounds() -> None:
    with pytest.raises(PydanticValidationError):
        _settings(relevance_threshold=1.5)
    assert _settings(relevance_threshold=0.0).relevance_threshold == 0.0


def test_is_production_flag() -> None:
    assert _settings(env="production").is_production is True
    assert _settings(env="development").is_production is False


def test_env_prefix_reads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("IPSAKTI_RRF_K", "42")
    monkeypatch.setenv("IPSAKTI_ENV", "staging")
    s = Settings(_env_file=None)
    assert s.rrf_k == 42
    assert s.env == "staging"
