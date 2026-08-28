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
    # Default is gemini-2.5-flash per SIH26034 plan v2
    gemini_model: str = "gemini-2.5-flash"
    gemini_timeout_s: float = 12.0

    # --- Server --------------------------------------------------------------
    cors_origin: str = "http://localhost:3000"
    max_upload_mb: int = 12
    analysis_ttl_seconds: int = 3600

    # Longest edge before the image is sent to Gemini.
    max_image_edge_px: int = 1600

    # --- Confidence thresholds -----------------------------------------------
    ocr_field_min_confidence: float = 0.60
    extract_field_min_confidence: float = 0.55

    # --- Statutory constants -------------------------------------------------
    # EAN-13 nominal symbol width at 100% magnification, per ISO/IEC 15420.
    ean13_nominal_width_mm: float = 37.29

    # --- Persistence / Supabase ----------------------------------------------
    supabase_url: str = ""
    supabase_key: str = ""

    @property
    def extraction_available(self) -> bool:
        """False => services/extract.py serves the fixture extractor."""
        return bool(self.gemini_api_key.strip())

    @property
    def rules_catalogue_path(self) -> Path:
        return BACKEND_ROOT / "app" / "services" / "rules" / "catalogue.yaml"

    @property
    def exemptions_path(self) -> Path:
        return BACKEND_ROOT / "app" / "services" / "rules" / "exemptions.yaml"


@lru_cache
def get_settings() -> Settings:
    return Settings()
