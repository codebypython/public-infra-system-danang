"""AI service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class AISettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    use_real_model: bool = False
    model_path: str = "models/yolov8n.pt"
    confidence_threshold: float = 0.6
    max_image_bytes: int = 10 * 1024 * 1024


settings = AISettings()
