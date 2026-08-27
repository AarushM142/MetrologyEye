"""Scale recovery tests.

The plan's gate for this stage was "px_per_mm on a real barcode photo, within ±10% of a
ruler measurement". A synthetic EAN-13 lets us assert something stronger and repeatable:
the *exact* expected ratio, since we know the module width we rendered.

What these tests deliberately do NOT assert is that px_per_mm is physically correct for a
real package. It cannot be — print magnification is unknown. They assert the arithmetic is
right given the stated 100% assumption, which is a different and honest claim.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.config import get_settings
from app.schemas import ScaleSource
from app.services.scale import (
    _bar_profile,
    _MIN_BARS_LOCATED,
    _valid_ean13,
    detect_scale,
    manual_scale,
)
from tests.synth import SYMBOL_MODULES, render_ean13, render_label

# Check digit computed by tests.synth.ean13_checksum and asserted below, so a typo here
# cannot masquerade as a detector failure.
VALID_CODE = "8901234567890"


def test_checksum_accepts_valid_code():
    assert _valid_ean13(VALID_CODE)


@pytest.mark.parametrize("code", ["8901234567894", "890123456789", "abcdefghijklm", ""])
def test_checksum_rejects_invalid_codes(code: str):
    assert not _valid_ean13(code)


@pytest.mark.parametrize("module_px", [2, 3, 4, 6])
def test_px_per_mm_matches_rendered_module_width(module_px: int):
    """Scale must track the symbol's rendered size across print magnifications.

    The barcode is embedded in a full label rather than tested bare: that is the
    composition production sees, and a barcode filling its own frame is not.
    """
    image = render_label(
        [("NET QUANTITY 500 g", 0.9), ("MRP Rs. 145.00", 0.8)],
        barcode=VALID_CODE,
        module_px=module_px,
        width=1200,
    )

    scale = detect_scale(image)
    assert scale is not None, f"barcode not detected at module_px={module_px}"

    expected = (SYMBOL_MODULES * module_px) / get_settings().ean13_nominal_width_mm
    assert scale.px_per_mm == pytest.approx(expected, rel=0.10)
    assert scale.source is ScaleSource.EAN13


@pytest.mark.parametrize("module_px", [2, 3, 4, 6])
def test_bar_profile_recovers_span_exactly_and_counts_thirty_bars(module_px: int):
    """The measurement that px/mm rests on, tested directly rather than through detection.

    An EAN-13 symbol has exactly 30 bars. Asserting the count — not just the span — is what
    distinguishes "measured a barcode" from "measured something barcode-shaped", and it is
    the check that makes the undecoded path in `detect_scale` safe.
    """
    symbol = render_ean13(VALID_CODE, module_px=module_px)
    gray = cv2.cvtColor(symbol, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    whole_frame = np.array([[0, height], [0, 0], [width, 0], [width, height]])

    profile = _bar_profile(gray, whole_frame)
    assert profile is not None
    span, bars = profile

    assert span == SYMBOL_MODULES * module_px  # exact, not approximate
    assert bars == 30


def test_bar_profile_rejects_a_text_block():
    """Text must not measure as a barcode — otherwise a paragraph sets the scale.

    Text yields no full-height dark columns at all, which is why the 0.5 dark-fraction
    threshold is the right discriminator rather than a mere edge count.
    """
    label = render_label(
        [("Plot 14, MIDC Area, Nashik, Maharashtra 422007", 0.55)], barcode=None, width=1200
    )
    gray = cv2.cvtColor(label, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    whole_frame = np.array([[0, height], [0, 0], [width, 0], [width, height]])

    profile = _bar_profile(gray, whole_frame)
    assert profile is None or profile[1] < _MIN_BARS_LOCATED


def test_partial_barcode_detection_is_rejected_on_the_undecoded_path():
    """A half-covered symbol is the dangerous case: it measures cleanly and is simply wrong.

    OpenCV really does return such quads — a truncated detection on a synthetic label
    measured 224 px against 442 px for the same barcode. Because the crop contains real
    bars, span measurement succeeds and the resulting px/mm looks entirely plausible while
    being off by ~2x. Only the bar count catches it, so guard that behaviour here.
    """
    symbol = render_ean13(VALID_CODE, module_px=4)
    gray = cv2.cvtColor(symbol, cv2.COLOR_BGR2GRAY)
    height, width = gray.shape[:2]
    half = np.array([[0, height], [0, 0], [width // 2, 0], [width // 2, height]])

    profile = _bar_profile(gray, half)
    assert profile is not None, "a half symbol still contains measurable bars"
    span, bars = profile

    assert span < SYMBOL_MODULES * 4 * 0.75  # measurably short of the true span
    assert bars < _MIN_BARS_LOCATED, "partial detections must fail the bar-count gate"


def test_valid_barcode_is_decoded_not_merely_located():
    """A decoded symbol earns higher confidence than a located-only one; make sure the
    synthetic barcode really is valid EAN-13 so tests exercise the stronger path."""
    image = render_label(
        [("NET QUANTITY 500 g", 0.9)], barcode=VALID_CODE, module_px=3, width=1200
    )
    scale = detect_scale(image)
    assert scale is not None
    assert scale.barcode_value == VALID_CODE


def test_scale_is_reported_with_sub_unity_confidence():
    """Confidence must never claim certainty: the magnification assumption is unresolved."""
    image = render_label(
        [("NET QUANTITY 500 g", 0.9), ("MRP Rs. 145.00", 0.8)],
        barcode=VALID_CODE,
        module_px=3,
        width=1200,
    )
    scale = detect_scale(image)
    assert scale is not None
    assert 0.0 < scale.confidence < 1.0
    assert scale.assumed_magnification == 1.0
    assert "magnification" in scale.note


def test_no_barcode_returns_none_rather_than_a_guess():
    image = render_label([("NET QUANTITY 500 g", 0.9)], barcode=None)
    assert detect_scale(image) is None


def test_blank_image_returns_none():
    assert detect_scale(np.full((400, 400, 3), 255, np.uint8)) is None


def test_manual_scale_is_fully_trusted():
    """A human with a ruler outranks our inference — and the note must say so."""
    scale = manual_scale(7.5)
    assert scale.px_per_mm == 7.5
    assert scale.confidence == 1.0
    assert scale.source is ScaleSource.MANUAL
    assert "manually" in scale.note.lower()
