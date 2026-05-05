"""Strongly-typed application settings, sourced from environment / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised configuration; mirror of `.env.example`."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Core
    env: Literal["development", "staging", "production", "test"] = "development"
    debug: bool = True
    secret_key: str = "change-me-to-a-random-64-char-hex"
    cors_allow_origins: str = "http://localhost:3000"

    # Database
    database_url: str = "postgresql+asyncpg://infra:infra_dev_pw@localhost:5432/danang_infra"
    database_url_sync: str = "postgresql://infra:infra_dev_pw@localhost:5432/danang_infra"
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_echo: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # MinIO / S3
    s3_endpoint_url: str = "http://localhost:9000"
    s3_public_url: str = "http://localhost:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "danang-infra"
    s3_region: str = "ap-southeast-1"

    # Meilisearch
    meili_host: str = "http://localhost:7700"
    meili_master_key: str = "meili_dev_key"

    # AI Service
    ai_service_url: str = "http://localhost:8001"
    ai_use_real_model: bool = False
    ai_confidence_threshold: float = 0.6

    # JWT
    jwt_algorithm: str = "HS256"
    jwt_access_ttl_minutes: int = 15
    jwt_refresh_ttl_days: int = 7

    # Rate limiting
    rate_limit_login_per_15m: int = 5
    rate_limit_report_per_hour: int = 5

    # Map area — Đà Nẵng
    danang_bbox_min_lng: float = 107.95
    danang_bbox_min_lat: float = 15.95
    danang_bbox_max_lng: float = 108.45
    danang_bbox_max_lat: float = 16.20
    danang_center_lat: float = 16.0544
    danang_center_lng: float = 108.2022

    # Observability
    sentry_dsn: str | None = None
    log_level: str = "INFO"
    otel_exporter_otlp_endpoint: str | None = None

    # Email
    sendgrid_api_key: str | None = None
    mailgun_api_key: str | None = None
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_username: str | None = None
    smtp_password: str | None = None
    email_from: str = "noreply@danang.gov.vn"

    # External
    openaq_api_base: AnyHttpUrl = Field(default="https://api.openaq.org/v2")

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins_list(self) -> list[str]:
        """Comma-separated string -> list."""
        return [o.strip() for o in self.cors_allow_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings — call from FastAPI deps and modules."""
    return Settings()


settings = get_settings()
