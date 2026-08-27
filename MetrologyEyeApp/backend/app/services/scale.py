"""Physical scale recovery from an EAN-13 barcode.

The honest version of this problem: an EAN-13 symbol is nominally 37.29 mm wide, but
ISO/IEC 15420 permits printing it at roughly 80%-200% magnification, and packaged goods
use the whole range. So the barcode gives us a *plausible* px/mm, not a true one.

This module therefore returns confidence alongside the number, and the rules engine
treats every font-height finding derived from it as a WARNING. Anything else would mean
issuing a legal notice off an unvalidated assumption.
"""

from __future__ import annotations

import cv2
import numpy as np

from app.config import get_settings
from app.schemas import ScaleInfo, ScaleSource

# Confidence when a barcode is both located and decoded to a valid EAN-13. Capped well
# below 1.0 because the magnification assumption, not the measurement, is the error source.
CONFIDENCE_DECODED = 0.80
CONFIDENCE_LOCATED_ONLY = 0.45

# Blur kernels tried in order until the detector finds something.
#
# This is not defensive padding — it fixes a measured failure. OpenCV's barcode detector is
# gradient-based and needs edges with some spatial extent; a perfectly crisp square-wave
# edge produces a single-pixel gradient spike it misses entirely. Real photos are naturally
# soft enough, but our own `preprocess._enhance_contrast` (CLAHE) sharpens edges back up,
# and crisp scans or synthetic renders fail outright. Measured on a 1600 px synthetic label:
# 0 -> not detected, 3 -> detected and decoded. Cost is a few ms per extra attempt.
_BLUR_KERNELS = (0, 3, 5, 7)


def _valid_ean13(code: str) -> bool:
    """EAN-13 mod-10 checksum. Guards against a garbage decode setting the scale."""
    if len(code) != 13 or not code.isdigit():
        return False
    digits = [int(c) for c in code]
    checksum = sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12]))
    return (10 - checksum % 10) % 10 == digits[12]


def _quad_width_px(points: np.ndarray) -> float:
    """Long edge of a detected barcode quad, in pixels.

    Used only to prefer the larger of two competing detections. It is deliberately *not*
    used to compute px/mm — see `_bar_profile` for why the quad width is untrustworthy.
    """
    pts = points.reshape(4, 2).astype(np.float64)
    edges = [float(np.linalg.norm(pts[i] - pts[(i + 1) % 4])) for i in range(4)]
    edges.sort()
    # Opposite edges of a rectangle are equal; average the two longest.
    return (edges[2] + edges[3]) / 2.0


def _detect_once(detector: object, gray: np.ndarray) -> tuple[list[str], np.ndarray] | None:
    """One detection attempt. Returns (decoded values, quad points) or None.

    Note that `detectAndDecodeWithType` reports `ok=True` with an **empty** value string
    when it locates a candidate but cannot decode it. So `ok` alone does not mean "decoded",
    and the caller must inspect the values — see `detect_scale`.
    """
    try:
        ok, decoded, _types, points = detector.detectAndDecodeWithType(gray)  # type: ignore[attr-defined]
        if ok and points is not None:
            return (list(decoded) if decoded is not None else []), points
    except cv2.error:
        pass

    # Detection without decode still yields geometry, which is all scale needs.
    try:
        ok, points = detector.detect(gray)  # type: ignore[attr-defined]
    except cv2.error:
        return None
    if ok and points is not None:
        return [], points
    return None


# A column inside the barcode region counts as part of a bar when at least this fraction of
# its height is dark. 0.5 separates full-height bars from the human-readable digits printed
# beneath the symbol, which occupy far less of the column.
_BAR_COLUMN_DARK_FRACTION = 0.5

# A complete EAN-13 symbol contains exactly 30 bars, and the column profile recovers all 30
# across magnifications, blur and noise. The two thresholds below reflect how much other
# evidence we have that the region really is a barcode:
#
#   DECODED  - a valid mod-10 checksum over 13 digits already proves it. The bar count only
#              has to confirm the crop actually contains the symbol, so the bar is low.
#              (Measured: 2 px/module under a 7 px blur merges bars down to 16 while still
#              recovering the span exactly, so a strict count here would reject good data.)
#   LOCATED  - no decode means structure is the *only* evidence. Held near the true 30. This
#              is what rejects a text block (measures 0 full-height dark runs) and, more
#              importantly, a partial detection covering half the symbol (measures 18) —
#              which would otherwise yield a plausible-looking scale that is simply wrong.
_MIN_BARS_DECODED = 12
_MIN_BARS_LOCATED = 24


def _bar_profile(gray: np.ndarray, quad: np.ndarray) -> tuple[float, int] | None:
    """Measure the 95-module span in pixels, and count bars, from the bars themselves.

    Why not just use the detected quad width: OpenCV's quad tracks neither the symbol's
    width nor its height reliably. For one synthetic symbol it returned 441.6 px wide on a
    full detection and 224.4 px on a truncated one — the same barcode, a 2x disagreement —
    and its height covers only about half the bars. Deriving px/mm from it would inflate the
    scale, which *understates* every measured letter height and biases the font check toward
    false findings. Since a font finding lands in a legal notice, that bias is unacceptable.

    So: crop the detected region, threshold it, and find the first and last full-height dark
    columns. That recovers the rendered span at 0.0% error at 2, 3, 4 and 6 px per module,
    and holds under blur and noise, rather than to within a fudge factor.

    Returns (span_px, bar_count), or None when the region does not measure like a barcode.
    """
    points = quad.reshape(4, 2).astype(np.float64)
    x0, y0 = np.floor(points.min(axis=0)).astype(int)
    x1, y1 = np.ceil(points.max(axis=0)).astype(int)

    height, width = gray.shape[:2]
    x0, y0 = max(0, int(x0)), max(0, int(y0))
    x1, y1 = min(width, int(x1)), min(height, int(y1))
    if x1 - x0 < 20 or y1 - y0 < 8:
        return None

    crop = gray[y0:y1, x0:x1]
    _, binary = cv2.threshold(crop, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)
    dark = (binary.mean(axis=0) / 255.0) > _BAR_COLUMN_DARK_FRACTION
    columns = np.flatnonzero(dark)
    if columns.size == 0:
        return None

    # Count runs of dark columns — i.e. bars. A rising edge starts each one.
    bars = int(np.count_nonzero(dark[1:] & ~dark[:-1])) + int(dark[0])

    span = float(columns[-1] - columns[0] + 1)
    if span <= 20:
        return None
    return span, bars


def detect_scale(image: np.ndarray) -> ScaleInfo | None:
    """Locate an EAN-13 barcode and convert its width to px/mm.

    Returns None when no plausible barcode is found — the caller then sets `scale: null`
    and the rules engine suppresses font checks rather than guessing a scale.
    """
    settings = get_settings()

    try:
        detector = cv2.barcode.BarcodeDetector()
    except AttributeError:
        # Plain opencv-python instead of opencv-contrib-python. requirements.txt pins
        # contrib precisely to avoid this, but a stale env should degrade, not crash.
        return None

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image

    decoded: tuple[float, str] | None = None
    located: tuple[float, np.ndarray] | None = None

    # Run the whole cascade in search of a *decoded* symbol rather than stopping at the
    # first mere detection. A decode proves the region really is an EAN-13; an undecoded
    # quad can just as easily be a text block or half a barcode, and measuring either yields
    # a scale that is confidently wrong — the worst outcome for a font measurement.
    for kernel in _BLUR_KERNELS:
        candidate_gray = cv2.GaussianBlur(gray, (kernel, kernel), 0) if kernel else gray
        attempt = _detect_once(detector, candidate_gray)
        if attempt is None:
            continue
        values, points = attempt

        for index in range(len(points)):
            quad = np.asarray(points[index])
            if quad.size != 8:
                continue
            # Measure on the original frame, never the blurred one: the blur exists only to
            # make the detector see the edges, and measuring it back would soften the span.
            profile = _bar_profile(gray, quad)
            if profile is None:
                continue
            span, bars = profile

            value = values[index].strip() if index < len(values) else ""
            if _valid_ean13(value):
                if bars >= _MIN_BARS_DECODED:
                    decoded = (span, value)
                    break
            elif bars >= _MIN_BARS_LOCATED and (
                located is None or _quad_width_px(quad) > _quad_width_px(located[1])
            ):
                located = (span, quad)
        if decoded is not None:
            break

    measured = decoded or located
    if measured is None:
        return None

    px_per_mm = measured[0] / settings.ean13_nominal_width_mm
    if px_per_mm <= 0:  # pragma: no cover - span already checked positive
        return None

    return ScaleInfo(
        px_per_mm=round(px_per_mm, 4),
        confidence=CONFIDENCE_DECODED if decoded else CONFIDENCE_LOCATED_ONLY,
        source=ScaleSource.EAN13,
        assumed_magnification=1.0,
        barcode_value=decoded[1] if decoded else None,
    )


def manual_scale(px_per_mm: float) -> ScaleInfo:
    """Scale supplied by the operator via the calibration slider.

    Confidence is 1.0 — a human with a ruler outranks our barcode inference, and the UI
    only offers this when they have measured something.
    """
    return ScaleInfo(
        px_per_mm=px_per_mm,
        confidence=1.0,
        source=ScaleSource.MANUAL,
        note="Scale set manually by the inspector. Font measurements use this value.",
    )
