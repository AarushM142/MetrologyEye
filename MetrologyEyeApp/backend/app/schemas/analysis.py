"""The `/api/analyze` response contract.

This module defines the API schema matching Plan v2 §4 and Phase 2.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.violations import BBox, DeclarationField, ExemptionResult, Finding, Severity


class ScaleSource(str, Enum):
    EAN13 = "ean13"
    REFERENCE_CARD = "reference_card"
    DUAL = "dual"
    MANUAL = "manual"  # operator overrode via the calibration slider
    NONE = "none"


class BarcodeScale(BaseModel):
    px_per_mm: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    assumed_magnification: float = Field(default=1.0)
    barcode_value: str | None = None


class ReferenceObjectScale(BaseModel):
    px_per_mm: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    type: str = Field(default="id_card")


class ScaleInfo(BaseModel):
    """Pixel-to-millimetre conversion with tiered confidence (Plan v2 §3.2).

    Tiers:
    - HIGH: both barcode and reference card present and agree within 10%
    - MEDIUM: exactly one reliable scale source is present
    - MANUAL_REQUIRED: neither source present or disagreement >25%
    """

    px_per_mm: float = Field(default=1.0, gt=0)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    source: ScaleSource = ScaleSource.EAN13
    tier: Literal["HIGH", "MEDIUM", "MANUAL_REQUIRED"] = "HIGH"
    barcode: BarcodeScale | None = None
    reference_object: ReferenceObjectScale | None = None
    assumed_magnification: float = Field(
        default=1.0,
        description="EAN-13 print magnification assumed when deriving scale (1.0 = 100%).",
    )
    barcode_value: str | None = None
    note: str = Field(
        default=(
            "Scale derived from EAN-13 nominal width (37.29 mm) assuming 100% print "
            "magnification. Font-size findings are advisory warnings, and manual verification is required if no reference resolves."
        )
    )


class Declaration(BaseModel):
    """One extracted mandatory declaration."""

    field: DeclarationField | str
    value: str
    bbox: BBox | None = None
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    ocr_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    extract_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_review: bool = Field(default=False)
    geometry_source: Literal["ocr", "vlm", "none"] = "none"
    text_height_mm: float | None = Field(
        default=None,
        description="Measured cap height in mm. Requires geometry_source='ocr' and a scale.",
    )


class ImageMeta(BaseModel):
    width: int
    height: int
    preview_url: str = Field(description="GET endpoint serving the preprocessed image")


class Summary(BaseModel):
    violations: int = 0
    warnings: int = 0
    manual_required: int = 0
    compliant: int = 0


class Timings(BaseModel):
    """Per-stage latency in milliseconds."""

    preprocess: int = 0
    scale: int = 0
    ocr: int = 0
    extract: int = 0
    rules: int = 0
    total: int = 0


class DegradationFlag(str, Enum):
    """Why a run was less than fully capable."""

    NO_BARCODE = "no_barcode"
    NO_SCALE_REFERENCE = "no_scale_reference"
    BLURRY_IMAGE = "blurry_image"
    GLARED_IMAGE = "glared_image"
    LOW_RESOLUTION = "low_resolution"
    OCR_UNAVAILABLE = "ocr_unavailable"
    EXTRACT_MOCKED = "extract_mocked"
    EXTRACT_FAILED = "extract_failed"
    PARTIAL_TEXT = "partial_text"


class AnalyzeResponse(BaseModel):
    analysis_id: str
    source: Literal["upload", "url"] = "upload"
    image: ImageMeta
    extraction_status: str = Field(default="ok", description="'ok' or 'unavailable'")
    manual_fallback: bool = Field(
        default=False, description="True when the VLM is unavailable and demo fixtures are served."
    )
    scale: ScaleInfo | None = Field(
        default=None, description="Null when no scale reference was found."
    )
    exemptions_evaluated: list[ExemptionResult] = Field(default_factory=list)
    declarations: list[Declaration] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    summary: Summary = Field(default_factory=Summary)
    timings_ms: Timings = Field(default_factory=Timings)
    degraded: list[DegradationFlag] = Field(default_factory=list)
    manual_inspection_required: bool = Field(
        default=False,
        description="True when degradation or tier is severe enough that a human must review.",
    )
    raw_extraction: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Audit trail: the structured values the AI verification layer returned. "
            "Persisted verbatim to local storage; not rendered in the notice."
        ),
    )

    @property
    def violations(self) -> list[Finding]:
        """Convenience alias matching Plan v2 contract."""
        return self.findings

    def recount(self) -> "AnalyzeResponse":
        """Recompute `summary` from `findings`. Single source of truth for the counts."""
        self.summary = Summary(
            violations=sum(f.severity is Severity.VIOLATION for f in self.findings),
            warnings=sum(f.severity is Severity.WARNING for f in self.findings),
            manual_required=sum(f.severity is Severity.MANUAL_REQUIRED for f in self.findings),
            compliant=sum(f.severity is Severity.COMPLIANT for f in self.findings),
        )
        return self


class UrlIngestRequest(BaseModel):
    url: str


class NoticeRequest(BaseModel):
    analysis_id: str
    inspector_name: str | None = None
    inspector_designation: str | None = None
    premises: str | None = None


class NoticeReviewRequest(BaseModel):
    """Stub auth: a reviewer is identified by an opaque string for now."""

    reviewer_id: str
