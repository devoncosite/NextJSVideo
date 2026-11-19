"""Environment Configuration & Validation Harness (TASK-0.3)."""

from __future__ import annotations

from functools import lru_cache
from typing import Dict, List, Literal, Optional
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def mask_secret(value: Optional[str]) -> str:
    """Safely mask secret API keys or tokens for logs and diagnostics."""
    if not value or not value.strip():
        return "NOT_SET"
    clean = value.strip()
    if len(clean) <= 8:
        return "****"
    return f"{clean[:4]}...{clean[-4:]}"


class Settings(BaseSettings):
    """Strict application configuration validated via Pydantic v2 BaseSettings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Runtime Environment
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    APP_NAME: str = "CineForge Enterprise AI Video Engine"
    API_V1_PREFIX: str = "/api/v1"

    # Database Configuration (PostgreSQL 16 + asyncpg)
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://studio:studio_secret_pw@127.0.0.1:5432/studio_db",
        description="Async SQLAlchemy connection string",
    )
    DB_POOL_SIZE: int = Field(default=20, ge=1, le=200)
    DB_MAX_OVERFLOW: int = Field(default=10, ge=0, le=100)
    DB_POOL_RECYCLE: int = Field(default=1800, ge=60)
    DB_POOL_PRE_PING: bool = True

    # Redis & ARQ Queue
    REDIS_URL: str = Field(
        default="redis://127.0.0.1:6379/0",
        description="Redis connection URL for ARQ workers and pub/sub deltas",
    )

    # S3 / Cloudflare R2 / MinIO Object Storage
    S3_ENDPOINT_URL: str = Field(default="http://127.0.0.1:9000")
    S3_PUBLIC_CDN_URL: str = Field(default="http://127.0.0.1:9000/studio-assets")
    S3_BUCKET_NAME: str = Field(default="studio-assets")
    S3_REGION: str = Field(default="us-east-1")
    S3_ACCESS_KEY: str = Field(default="minioadmin")
    S3_SECRET_KEY: str = Field(default="minioadmin_secret")

    # Security & JWT
    JWT_SECRET_KEY: str = Field(
        default="dev_jwt_secret_key_change_in_production_32chars",
        min_length=16,
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # AI Provider API Keys
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    REPLICATE_API_TOKEN: Optional[str] = None
    FAL_KEY: Optional[str] = None
    ELEVENLABS_API_KEY: Optional[str] = None
    SYNCLABS_API_KEY: Optional[str] = None

    @field_validator("DATABASE_URL")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        if not v or not isinstance(v, str):
            raise ValueError("DATABASE_URL must be a non-empty string")
        allowed_schemes = (
            "postgresql+asyncpg://",
            "postgresql://",
            "sqlite+aiosqlite://",
        )
        if not v.startswith(allowed_schemes):
            raise ValueError(
                f"DATABASE_URL must start with one of {allowed_schemes}; received '{v}'"
            )
        parsed = urlparse(v)
        if v.startswith("postgresql") and (not parsed.hostname or not parsed.path or parsed.path == "/"):
            raise ValueError(
                "Malformed PostgreSQL DATABASE_URL: hostname and database name are required"
            )
        return v

    @field_validator("REDIS_URL")
    @classmethod
    def validate_redis_url(cls, v: str) -> str:
        if not v.startswith(("redis://", "rediss://")):
            raise ValueError("REDIS_URL must start with redis:// or rediss://")
        return v

    def get_missing_provider_keys(self) -> List[str]:
        """Return list of provider API key names that are currently unset or empty."""
        provider_fields = [
            "GEMINI_API_KEY",
            "ANTHROPIC_API_KEY",
            "REPLICATE_API_TOKEN",
            "FAL_KEY",
            "ELEVENLABS_API_KEY",
            "SYNCLABS_API_KEY",
        ]
        missing: List[str] = []
        for key in provider_fields:
            val = getattr(self, key, None)
            if not val or not str(val).strip():
                missing.append(key)
        return missing

    def to_masked_dict(self) -> Dict[str, object]:
        """Return sanitized diagnostic dictionary with all secrets masked."""
        return {
            "environment": self.ENVIRONMENT,
            "appName": self.APP_NAME,
            "databaseUrl": self._mask_connection_url(self.DATABASE_URL),
            "redisUrl": self._mask_connection_url(self.REDIS_URL),
            "s3EndpointUrl": self.S3_ENDPOINT_URL,
            "s3PublicCdnUrl": self.S3_PUBLIC_CDN_URL,
            "s3BucketName": self.S3_BUCKET_NAME,
            "s3Region": self.S3_REGION,
            "s3AccessKey": mask_secret(self.S3_ACCESS_KEY),
            "s3SecretKey": mask_secret(self.S3_SECRET_KEY),
            "jwtSecretKey": mask_secret(self.JWT_SECRET_KEY),
            "providers": {
                "GEMINI_API_KEY": mask_secret(self.GEMINI_API_KEY),
                "ANTHROPIC_API_KEY": mask_secret(self.ANTHROPIC_API_KEY),
                "REPLICATE_API_TOKEN": mask_secret(self.REPLICATE_API_TOKEN),
                "FAL_KEY": mask_secret(self.FAL_KEY),
                "ELEVENLABS_API_KEY": mask_secret(self.ELEVENLABS_API_KEY),
                "SYNCLABS_API_KEY": mask_secret(self.SYNCLABS_API_KEY),
            },
            "missingProviderKeys": self.get_missing_provider_keys(),
        }

    @staticmethod
    def _mask_connection_url(url: str) -> str:
        parsed = urlparse(url)
        if parsed.password:
            return url.replace(f":{parsed.password}@", ":****@")
        return url


@lru_cache
def get_settings() -> Settings:
    """Return cached Settings instance."""
    return Settings()
