"""The `/api/analyze` response contract.

This module is frozen early on purpose: the four frontend screens are built against
these shapes while the CV and extraction services are still being written.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.violations import BBox, DeclarationField, Finding, Severity


class ScaleSource(str, Enum):
    EAN13 = "ean13"
    MANUAL = "manual"  # operator overrode via the calibration slider
    NONE = "none"


class ScaleInfo(BaseModel):
    """Pixel-to-millimetre conversion, with its uncertainty made explicit.

    An EAN-13 symbol is nominally 37.29 mm wide, but the standard permits printing at
    roughly 80%-200% magnification. We therefore cannot derive a *true* millimetre scale
    from a barcode alone. `assumed_magnification` records the assumption, `confidence`
    records how much to trust it, and `note` is printed verbatim on the PDF notice so
    the assumption is never silently load-bearing.
    """

    px_per_mm: float = Field(gt=0)
    confidence: float = Field(ge=0.0, le=1.0)
    source: ScaleSource
    assumed_magnification: float = Field(
        default=1.0,
        description="EAN-13 print magnification assumed when deriving scale (1.0 = 100%).",
    )
    barcode_value: str | None = None
    note: str = Field(
        default=(
            "Scale derived from EAN-13 nominal width (37.29 mm) assuming 100% print "
            "magnification. Font-size findings are advisory warnings, not violations."
        )
    )


class Declaration(BaseModel):
    """One extracted mandatory declaration.

    `geometry_source` matters: "ocr" boxes are precise enough to measure text height
    against a statutory minimum, "vlm" boxes are approximate and suppress the font
    check. Never conflate the two.
    """

    field: DeclarationField
    value: str
    bbox: BBox | None = None
    confidence: float = Field(ge=0.0, le=1.0)
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
    compliant: int = 0


class Timings(BaseModel):
    """Per-stage latency. Shipped in every response so the <3s NFR is observable
    rather than asserted."""

    preprocess: int = 0
    scale: int = 0
    ocr: int = 0
    extract: int = 0
    rules: int = 0
    total: int = 0


class DegradationFlag(str, Enum):
    """Why a run was less than fully capable. Drives the manual-inspection prompt
    required by NFR-3 — the pipeline degrades and says so, it does not crash or
    fabricate."""

    NO_BARCODE = "no_barcode"  # scale is null; font checks suppressed
    BLURRY_IMAGE = "blurry_image"
    LOW_RESOLUTION = "low_resolution"
    OCR_UNAVAILABLE = "ocr_unavailable"
    EXTRACT_MOCKED = "extract_mocked"  # no GEMINI_API_KEY; fixture extractor used
    EXTRACT_FAILED = "extract_failed"
    PARTIAL_TEXT = "partial_text"


class AnalyzeResponse(BaseModel):
    analysis_id: str
    source: Literal["upload", "url"]
    image: ImageMeta
    scale: ScaleInfo | None = Field(
        default=None, description="Null when no barcode was found; font checks are then skipped."
    )
    declarations: list[Declaration] = []
    findings: list[Finding] = []
    summary: Summary = Summary()
    timings_ms: Timings = Timings()
    degraded: list[DegradationFlag] = []
    manual_inspection_required: bool = Field(
        default=False,
        description="True when degradation is severe enough that a human must review.",
    )

    def recount(self) -> "AnalyzeResponse":
        """Recompute `summary` from `findings`. Single source of truth for the counts."""
        self.summary = Summary(
            violations=sum(f.severity is Severity.VIOLATION for f in self.findings),
            warnings=sum(f.severity is Severity.WARNING for f in self.findings),
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
