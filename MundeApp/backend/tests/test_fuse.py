"""Fusion tests — the join between VLM semantics and OCR geometry.

Words are hand-built rather than read from a rendered label: fusion's job is the matching
logic, and feeding it fixed input makes these tests deterministic, fast, and independent of
whatever PaddleOCR happens to transcribe.

The bug that motivated most of this file: `_best_window` scored candidate windows with
`token_set_ratio` and kept the highest score. Because that scorer ignores surplus tokens, a
window containing the target *plus* five unrelated lines scores the same 100 as the target
alone — and the widest such window won. Declarations came back with boxes 211 px tall for
21 px lines, spanning from the top of the label down to the real text. In a Form-I notice
that is a red rectangle over six lines of someone's packaging.
"""

from __future__ import annotations

import pytest

from app.schemas import DeclarationField, ScaleSource
from app.services.fuse import MATCH_THRESHOLD, _best_window, fuse
from app.services.ocr import OcrWord
from app.services.scale import manual_scale

# A label transcribed as lines, with the OCR noise a real read produces ("Feods" for
# "Foods", "O" for "@") so the fuzzy matching is actually under test.
LINES = [
    ("SURAJ REFINED SUNFLOWER OIL", 28, 25),
    ("Net Quantity: 500 gms", 75, 27),
    ("MRP Rs.145.00", 122, 24),
    ("Mfd: 03/2026", 167, 26),
    ("Mfd by Suraj Feods Private Limited,", 218, 21),
    ("Plot 14, MIDC Area, Nashik, Maharashtra 422007", 265, 21),
]


def _words() -> list[OcrWord]:
    return [
        OcrWord(text=text, bbox=(30, y, 10 * len(text), height), confidence=0.9, cap_height_px=height * 0.72)
        for text, y, height in LINES
    ]


def _line_bbox(index: int) -> tuple[int, int, int, int]:
    text, y, height = LINES[index]
    return (30, y, 10 * len(text), height)


@pytest.mark.parametrize(
    ("value", "line_index"),
    [
        ("Refined Sunflower Oil", 0),
        ("500 gms", 1),
        ("Rs. 145.00", 2),
        ("03/2026", 3),
        ("Suraj Foods Private Limited", 4),
        ("Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007", 5),
    ],
)
def test_value_matches_exactly_one_line(value: str, line_index: int):
    """Each extracted value must land on its own line and no more.

    This is the assertion the sprawling-box bug failed: it matched the right *text* while
    returning geometry that also covered every line above it.
    """
    match = _best_window(value, _words())
    assert match is not None, f"{value!r} did not match"
    window, score = match

    assert len(window) == 1, (
        f"{value!r} matched {len(window)} lines; expected a single tight window. "
        f"Matched: {[w.text for w in window]}"
    )
    assert window[0].bbox == _line_bbox(line_index)
    assert score >= MATCH_THRESHOLD


def test_extracted_value_may_be_a_subset_of_the_printed_line():
    """The scorer must tolerate the label's own prefix wording.

    "Net Quantity: 500 gms" is printed; Gemini returns "500 gms". Scorers that penalise the
    surplus tokens score this pairing at 51.9 and drop the match — which would silently
    remove geometry from the field most likely to carry a violation.
    """
    match = _best_window("500 gms", _words())
    assert match is not None
    window, _ = match
    assert window[0].text == "Net Quantity: 500 gms"


def test_unrelated_value_does_not_match():
    """A value absent from the label must yield no geometry rather than a nearest guess."""
    assert _best_window("Country of Origin: Malaysia", _words()) is None


def test_empty_value_does_not_match():
    assert _best_window("", _words()) is None


def test_fuse_reports_ocr_geometry_and_millimetre_height():
    scale = manual_scale(10.0)
    declarations = fuse(
        {DeclarationField.NET_QUANTITY: "500 gms", DeclarationField.MRP: "Rs. 145.00"},
        _words(),
        scale,
    )

    by_field = {d.field: d for d in declarations}
    net = by_field[DeclarationField.NET_QUANTITY]

    assert net.geometry_source == "ocr"
    assert net.bbox == _line_bbox(1)
    # cap_height_px is 27 * 0.72 = 19.44; at 10 px/mm that is 1.944 mm.
    assert net.text_height_mm == pytest.approx(1.944, abs=0.001)


def test_unmatched_value_keeps_its_text_but_reports_no_geometry():
    """Losing the box must not lose the declaration — the value is still evidence of what
    the label says, and the rules engine still checks it. Only the font check is suppressed."""
    declarations = fuse(
        {DeclarationField.COUNTRY_OF_ORIGIN: "Malaysia"}, _words(), manual_scale(10.0)
    )

    (only,) = declarations
    assert only.value == "Malaysia"
    assert only.geometry_source == "none"
    assert only.bbox is None
    assert only.text_height_mm is None


def test_no_scale_means_no_height_even_when_the_box_is_known():
    """Without px/mm a pixel height cannot become a millimetre claim."""
    declarations = fuse({DeclarationField.NET_QUANTITY: "500 gms"}, _words(), None)
    (only,) = declarations
    assert only.geometry_source == "ocr"
    assert only.bbox is not None
    assert only.text_height_mm is None


def test_no_ocr_words_still_yields_declarations():
    """OCR unavailable is a degradation, not a failure: values survive without geometry."""
    declarations = fuse({DeclarationField.NET_QUANTITY: "500 gms"}, [], manual_scale(10.0))
    (only,) = declarations
    assert only.value == "500 gms"
    assert only.geometry_source == "none"


def test_declaration_order_follows_the_schema_not_the_dict():
    """Response order must be stable across runs, so it comes from DeclarationField order."""
    forwards = {
        DeclarationField.MRP: "Rs. 145.00",
        DeclarationField.NET_QUANTITY: "500 gms",
        DeclarationField.COMMODITY_NAME: "Refined Sunflower Oil",
    }
    backwards = dict(reversed(list(forwards.items())))

    fields_a = [d.field for d in fuse(forwards, _words(), None)]
    fields_b = [d.field for d in fuse(backwards, _words(), None)]

    assert fields_a == fields_b
    assert fields_a == sorted(fields_a, key=list(DeclarationField).index)


def test_fusion_is_deterministic():
    scale = manual_scale(10.0)
    values = {
        DeclarationField.NET_QUANTITY: "500 gms",
        DeclarationField.MANUFACTURER_NAME: "Suraj Foods Private Limited",
        DeclarationField.COUNTRY_OF_ORIGIN: "Malaysia",
    }
    runs = [
        [d.model_dump() for d in fuse(values, _words(), scale)] for _ in range(5)
    ]
    assert all(run == runs[0] for run in runs)


def test_located_declaration_is_more_confident_than_an_unlocated_one():
    """Corroboration between two independent readers is real evidence; reflect it."""
    scale = manual_scale(10.0)
    located = fuse({DeclarationField.NET_QUANTITY: "500 gms"}, _words(), scale)[0]
    unlocated = fuse({DeclarationField.COUNTRY_OF_ORIGIN: "Malaysia"}, _words(), scale)[0]
    assert located.confidence > unlocated.confidence


def test_manual_scale_is_usable_by_fusion():
    """Guards the seam between the calibration slider and millimetre heights."""
    scale = manual_scale(20.0)
    assert scale.source is ScaleSource.MANUAL
    declaration = fuse({DeclarationField.NET_QUANTITY: "500 gms"}, _words(), scale)[0]
    # Twice the px/mm must halve the reported height.
    assert declaration.text_height_mm == pytest.approx(0.972, abs=0.001)
