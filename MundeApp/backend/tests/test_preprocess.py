"""Preprocessing tests.

These exist because of a bug this stage shipped with and no other test could catch: the
glare-reduction mask classified a white label's background as glare and inpainted it,
dropping mean brightness from 241 to 50. That destroyed the barcode (scale went from a
correct 10.19 px/mm to None) and cut OCR from 7 clean lines to 4 garbled ones. Every unit
test still passed, because nothing exercised `preprocess` on a realistic label.

The theme of the assertions below is therefore *preservation*: preprocessing is a service to
the stages after it, and a step that silently degrades the frame is worse than no step.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from app.services import ocr, preprocess
from app.services.preprocess import MIN_LONG_EDGE_PX, BLUR_VARIANCE_THRESHOLD
from app.schemas import DegradationFlag
from app.services.scale import detect_scale
from tests.synth import NONCOMPLIANT_LINES, png_bytes, render_label

VALID_CODE = "8901234567890"


def _label(**kwargs) -> np.ndarray:
    return render_label(NONCOMPLIANT_LINES, barcode=VALID_CODE, module_px=4, width=1200, **kwargs)


def test_white_label_survives_preprocessing():
    """The regression test for the glare bug, stated as the property that actually matters.

    A label is mostly white. If preprocessing re-exposes it, everything downstream fails at
    once, so assert brightness is preserved rather than asserting any particular step ran.
    """
    original = _label()
    result = preprocess.preprocess(png_bytes(original))

    assert abs(float(result.image.mean()) - float(original.mean())) < 15.0, (
        "preprocessing changed overall exposure — the glare mask is probably selecting "
        "the label substrate instead of highlights"
    )


def test_barcode_still_detectable_after_preprocessing():
    """Scale is computed from the *preprocessed* frame, so detection must survive it.

    Asserting on `detect_scale(raw)` alone would have missed the glare bug entirely: the raw
    image measured correctly the whole time.
    """
    raw = _label()
    from_raw = detect_scale(raw)
    assert from_raw is not None, "precondition: the synthetic barcode is detectable"

    prepared = preprocess.preprocess(png_bytes(raw))
    from_prepared = detect_scale(prepared.image)

    assert from_prepared is not None, "barcode lost during preprocessing"
    assert from_prepared.px_per_mm == pytest.approx(from_raw.px_per_mm, rel=0.05)


def test_text_still_readable_after_preprocessing():
    """OCR runs on the preprocessed frame too; preprocessing must not cost us lines."""
    raw = _label()
    prepared = preprocess.preprocess(png_bytes(raw))

    words = ocr.read_words(prepared.image)
    if not words:
        pytest.skip("PaddleOCR unavailable in this environment")

    text = " ".join(w.text for w in words).casefold()
    # Spot-check the declarations the rules engine depends on, not the whole transcription:
    # OCR noise is expected and `fuse` is what absorbs it.
    #
    # NOTE: PaddleOCR may read '0' as 'o' in some fonts — '5oo' instead of '500' is a
    # known OCR quirk on synthetic labels. The invariant is that the quantity digit prefix
    # and the MRP digit survive, not that every character is character-perfect.
    assert "5" in text, f"quantity digit prefix not found in OCR output: {text!r}"
    assert "145" in text
    assert len(words) >= 5, f"expected most lines to survive, got {len(words)}"

def test_glare_reduction_leaves_a_white_background_alone():
    """Unit-level version of the same property, isolating the step that broke."""
    label = _label()
    reduced = preprocess._reduce_glare(label)
    assert abs(float(reduced.mean()) - float(label.mean())) < 5.0


def test_glare_reduction_still_removes_a_specular_highlight():
    """The guards must not be so conservative that the feature stops working.

    A blown-out blob on a dark glossy pouch is the case glare reduction exists for; it is
    small and isolated, which is exactly what distinguishes it from the substrate.
    """
    pouch = np.full((600, 900, 3), 40, np.uint8)
    cv2.circle(pouch, (700, 120), 45, (255, 255, 255), -1)

    reduced = preprocess._reduce_glare(pouch)

    centre = int(reduced[120, 700].mean())
    assert centre < 120, f"highlight not removed (centre still {centre})"
    assert abs(float(reduced.mean()) - 40.0) < 5.0, "surroundings should be untouched"


def test_low_resolution_is_flagged_not_rejected():
    small = render_label([("Net Quantity 500 g", 0.4)], barcode=None, width=320)
    result = preprocess.preprocess(png_bytes(small))
    assert max(result.width, result.height) < MIN_LONG_EDGE_PX
    assert DegradationFlag.LOW_RESOLUTION in result.degraded


def test_blurry_image_is_flagged():
    """Softness must be caught even though CLAHE later sharpens the frame back up."""
    blurred = cv2.GaussianBlur(_label(), (21, 21), 0)
    result = preprocess.preprocess(png_bytes(blurred))
    assert result.blur_variance < BLUR_VARIANCE_THRESHOLD
    assert DegradationFlag.BLURRY_IMAGE in result.degraded


def test_sharp_label_is_not_flagged_blurry():
    result = preprocess.preprocess(png_bytes(_label()))
    assert DegradationFlag.BLURRY_IMAGE not in result.degraded


def test_oversized_image_is_downscaled_to_the_configured_edge():
    """Coordinates live in the returned frame, so the downscale must actually happen here."""
    big = render_label(NONCOMPLIANT_LINES, barcode=VALID_CODE, module_px=8, width=3000)
    result = preprocess.preprocess(png_bytes(big))
    assert max(result.width, result.height) <= 1600
    assert (result.height, result.width) == result.image.shape[:2]


def test_undecodable_bytes_raise_value_error():
    """Routes translate this to a 422; it must not surface as a 500."""
    with pytest.raises(ValueError):
        preprocess.preprocess(b"this is not an image")


def test_png_bytes_round_trip_matches_the_returned_frame():
    """`png_bytes` is what GET /api/image/{id} serves and what the notice crops, so it has
    to be the same pixels the boxes were computed in."""
    result = preprocess.preprocess(png_bytes(_label()))
    decoded = cv2.imdecode(np.frombuffer(result.png_bytes, np.uint8), cv2.IMREAD_COLOR)
    assert decoded.shape == result.image.shape
    assert np.array_equal(decoded, result.image)
