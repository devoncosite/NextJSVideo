"""Tests for Environment Configuration & Validation Harness (TASK-0.3)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from server.core.config import Settings, mask_secret


def test_malformed_database_url_fails_to_boot() -> None:
    """Server settings must reject malformed DATABASE_URL values on boot."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(DATABASE_URL="mysql://root:pass@localhost/studio")
    assert "DATABASE_URL" in str(exc_info.value)

    with pytest.raises(ValidationError):
        Settings(DATABASE_URL="postgresql+asyncpg://localhost/")


def test_malformed_redis_url_fails_to_boot() -> None:
    with pytest.raises(ValidationError):
        Settings(REDIS_URL="http://localhost:6379/0")


def test_mask_secret_helper() -> None:
    assert mask_secret(None) == "NOT_SET"
    assert mask_secret("") == "NOT_SET"
    assert mask_secret("short") == "****"
    assert mask_secret("sk-proj-1234567890abcdef") == "sk-p...cdef"


def test_missing_provider_keys_detection() -> None:
    settings = Settings(
        GEMINI_API_KEY="AIzaSyTestKey123456789",
        FAL_KEY="fal_secret_key_987654321",
        ANTHROPIC_API_KEY=None,
        REPLICATE_API_TOKEN="",
    )
    missing = settings.get_missing_provider_keys()
    assert "GEMINI_API_KEY" not in missing
    assert "FAL_KEY" not in missing
    assert "ANTHROPIC_API_KEY" in missing
    assert "REPLICATE_API_TOKEN" in missing


def test_config_to_masked_dict_masks_secrets() -> None:
    settings = Settings()
    data = settings.to_masked_dict()
    assert "studio_secret_pw" not in str(data["databaseUrl"])
    assert ":****@" in str(data["databaseUrl"])
    assert "minioadmin_secret" not in str(data["s3SecretKey"])
    assert "..." in str(data["s3SecretKey"]) or data["s3SecretKey"] == "****"

