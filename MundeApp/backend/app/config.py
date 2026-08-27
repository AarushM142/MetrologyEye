"""Runtime configuration. Everything environment-dependent lives here."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- Gemini --------------------------------------------------------------
    gemini_api_key: str = ""
    # Deliberately not a code literal. gemini-1.5-flash is old enough that it may be
    # unavailable on newly issued keys; swapping models must stay a one-line env change.
    gemini_model: str = "gemini-1.5-flash"
    gemini_timeout_s: float = 20.0

    # --- Server --------------------------------------------------------------
    cors_origin: str = "http://localhost:3000"
    max_upload_mb: int = 12
    analysis_ttl_seconds: int = 3600

    # Longest edge before the image is sent to Gemini. First lever to pull if the
    # <3s end-to-end NFR is breached — extraction latency dominates the pipeline.
    max_image_edge_px: int = 1600

    # --- Statutory constants -------------------------------------------------
    # EAN-13 nominal symbol width at 100% magnification, per ISO/IEC 15420.
    # Used by services/scale.py as the physical reference for px->mm.
    ean13_nominal_width_mm: float = 37.29

    @property
    def extraction_available(self) -> bool:
        """False => services/extract.py serves the fixture extractor and the response
        is flagged degraded=[EXTRACT_MOCKED]. The pipeline stays runnable without a key."""
        return bool(self.gemini_api_key.strip())

    @property
    def rules_catalogue_path(self) -> Path:
        return BACKEND_ROOT / "app" / "services" / "rules" / "catalogue.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
