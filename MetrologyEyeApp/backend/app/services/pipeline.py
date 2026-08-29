"""Pipeline orchestration: bytes in, AnalyzeResponse out.

Stage order and the reason for it:

    preprocess (exposure + dewarp + deskew) -> scale -> ocr -> verify(ocr) -> fuse -> rules

Preprocessing now includes two new stages before OCR:
  - Exposure correction: gamma-adjusts underexposed/overexposed images so OCR confidence
    is not penalised by bad lighting when the label content is actually legible.
  - Curved-label dewarp: detects labels on cylindrical surfaces (bottles, cans) and applies
    a perspective correction so OCR works on a flat representation.

The VLM's role changed from independent extractor to OCR verifier:
  - OCR runs first and owns the geometry (word polygons for font-height rules).
  - The VLM receives the OCR full-text as primary evidence and verifies/corrects it,
    with the image available only to resolve ambiguous characters (0/O, rn/m, etc.).
  - `fuse.py` then attaches precise OCR boxes to the VLM-verified values.

Every stage is timed, and the timings ship in the response. The <3 s NFR is then
observable rather than asserted, and when it is missed the response says which stage
cost the time.
"""

from __future__ import annotations

import logging
import time
import uuid

from app.schemas import (
    AnalyzeResponse,
    DegradationFlag,
    ImageMeta,
    ScaleInfo,
    Timings,
)
from app.services import extract as extract_service
from app.services import fuse as fuse_service
from app.services import ocr as ocr_service
from app.services import preprocess as preprocess_service
from app.services import scale as scale_service
from app.services.rules import engine as rules_engine

logger = logging.getLogger(__name__)

# Degradations severe enough that a human must look at the package themselves. A blurry
# photo or failed extraction means we cannot vouch for the reading; NFR-3 requires we say
# so rather than present a confident-looking result.
_REQUIRES_MANUAL_REVIEW = frozenset(
    {
        DegradationFlag.BLURRY_IMAGE,
        DegradationFlag.LOW_RESOLUTION,
        DegradationFlag.EXTRACT_FAILED,
        DegradationFlag.PARTIAL_TEXT,
    }
)


class _Stopwatch:
    """Millisecond stage timer. Monotonic, so an NTP step mid-run cannot yield a negative."""

    def __init__(self) -> None:
        self.start = time.monotonic()
        self._mark = self.start

    def lap(self) -> int:
        now = time.monotonic()
        elapsed = int((now - self._mark) * 1000)
        self._mark = now
        return elapsed

    def total(self) -> int:
        return int((time.monotonic() - self.start) * 1000)


def analyze(
    image_bytes: bytes,
    source: str = "upload",
    manual_px_per_mm: float | None = None,
) -> tuple[AnalyzeResponse, bytes]:
    """Run the full pipeline.

    Returns the response and the preprocessed PNG, which the caller stores so
    `GET /api/image/{id}` and the notice's evidence crops both work from the exact frame
    the boxes were computed in.
    """
    watch = _Stopwatch()
    timings = Timings()
    degraded: list[DegradationFlag] = []

    # --- preprocess ---------------------------------------------------------------
    prepared = preprocess_service.preprocess(image_bytes)
    degraded.extend(prepared.degraded)
    if prepared.exposure_gamma != 1.0:
        logger.info(
            "exposure corrected: gamma=%.2f (mean L was %s)",
            prepared.exposure_gamma,
            "underexposed" if prepared.exposure_gamma < 1.0 else "overexposed",
        )
    if prepared.dewarp_applied:
        logger.info("curved-label dewarp applied: output %dx%d", prepared.width, prepared.height)
    timings.preprocess = watch.lap()

    # --- scale -------------------------------------------------------------------
    scale: ScaleInfo | None
    if manual_px_per_mm is not None:
        scale = scale_service.manual_scale(manual_px_per_mm)
    else:
        scale = scale_service.detect_scale(prepared.image)
        if scale is None:
            # Not an error. Font checks are suppressed downstream and the UI offers manual
            # calibration; fabricating a scale would be the actual failure.
            degraded.append(DegradationFlag.NO_BARCODE)
    timings.scale = watch.lap()

    # --- ocr ---------------------------------------------------------------------
    words = ocr_service.read_words(prepared.image)
    if not words:
        degraded.append(DegradationFlag.OCR_UNAVAILABLE)
    ocr_text = ocr_service.full_text(words)
    timings.ocr = watch.lap()

    # --- extract -----------------------------------------------------------------
    extraction = extract_service.extract(prepared.png_bytes, ocr_text=ocr_text)
    degraded.extend(extraction.degraded)
    # Advance the stopwatch regardless, but report the *precise* VLM call latency (ms)
    # rather than the whole-stage wall time, so timings_ms["extract"] reflects the actual
    # network+inference cost. Falls back to the stage time when no API call was made.
    elapsed_extract_ms = watch.lap()
    timings.extract = int(extraction.latency_ms) if extraction.latency_ms > 0 else elapsed_extract_ms

    # --- fuse + rules ------------------------------------------------------------
    declarations = fuse_service.fuse(
        extraction.values, words, scale, base_confidence=extraction.confidence
    )
    # Phase 6 pre-filter: exemptions are evaluated before the rule catalogue. The
    # results ship in the payload so an operator sees *why* rules were suppressed,
    # and the matched ones are passed into the engine to drive suppression.
    exemptions = rules_engine.evaluate_exemptions(declarations, full_text=extraction.full_text or ocr_text)
    findings = rules_engine.evaluate(
        declarations,
        full_text=extraction.full_text or ocr_text,
        scale=scale,
        exemptions=exemptions,
    )
    timings.rules = watch.lap()
    timings.total = watch.total()

    # Preserve first-seen order while de-duplicating: a flag can be raised by more than
    # one stage, and the UI should list each reason once.
    unique_degraded = list(dict.fromkeys(degraded))

    analysis_id = str(uuid.uuid4())
    response = AnalyzeResponse(
        analysis_id=analysis_id,
        source=source,  # type: ignore[arg-type]
        image=ImageMeta(
            width=prepared.width,
            height=prepared.height,
            preview_url=f"/api/image/{analysis_id}",
        ),
        scale=scale,
        declarations=declarations,
        findings=findings,
        exemptions_evaluated=exemptions,
        timings_ms=timings,
        degraded=unique_degraded,
        manual_inspection_required=bool(_REQUIRES_MANUAL_REVIEW.intersection(unique_degraded)),
        raw_extraction={
            "values": {k.value: v for k, v in extraction.values.items()},
            "full_text": extraction.full_text,
            "ocr_corrections": extraction.ocr_corrections,
        },
    ).recount()

    logger.info(
        "analysis %s: %d declarations, %d violations, %d warnings, %d ms total",
        analysis_id,
        len(declarations),
        response.summary.violations,
        response.summary.warnings,
        timings.total,
    )
    return response, prepared.png_bytes
