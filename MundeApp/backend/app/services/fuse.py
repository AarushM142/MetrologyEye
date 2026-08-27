"""Attach OCR geometry to Gemini-extracted values.

This module is the hinge of the whole design. Gemini knows *what* the label says; PaddleOCR
knows *where* each word sits and how tall it is. Neither alone can support a font-height
finding — the VLM's boxes are too coarse to measure millimetres, and OCR's transcription is
too unreliable to identify which text is the net-quantity declaration.

So: match each extracted value against consecutive OCR words by normalised similarity, and
take the geometry from the OCR side. A `Declaration` that fails to match keeps its value and
records `geometry_source="none"`, which suppresses its font check rather than measuring a
box we do not trust.
"""

from __future__ import annotations

import re
import statistics

from rapidfuzz import fuzz

from app.schemas import BBox, Declaration, DeclarationField, ScaleInfo
from app.services.ocr import OcrWord

# Below this similarity the match is more likely coincidence than correspondence, and a
# wrong box draws the inspector's eye at the wrong part of the label.
MATCH_THRESHOLD = 72.0

# Longest run of OCR words considered for one declaration. An address is the long case;
# beyond this the window cost grows without improving matches.
MAX_WINDOW = 14

_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    """Casefold and strip punctuation for comparison only.

    The original value is never modified — `net_quantity` in particular must stay verbatim
    ("500 gms" not "500 g"), because the printed form is the evidence.
    """
    return _SPACE.sub(" ", _PUNCT.sub(" ", text.casefold())).strip()


def _reading_order(words: list[OcrWord]) -> list[OcrWord]:
    # Row band before column, so a multi-column label yields runs of words that are
    # actually adjacent on the page.
    return sorted(words, key=lambda w: (w.bbox[1] // 12, w.bbox[0]))


def _union(boxes: list[BBox]) -> BBox:
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def _best_window(target: str, words: list[OcrWord]) -> tuple[list[OcrWord], float] | None:
    """Find the tightest run of consecutive OCR words most similar to `target`.

    `token_set_ratio` rather than plain ratio, because the extracted value is normally a
    *subset* of the printed line: the label reads "Net Quantity: 500 gms" while Gemini
    returns "500 gms". Scorers that penalise extra tokens score that pairing at 51.9 and
    lose the match entirely — measured — and net quantity is the field most likely to carry
    a violation. Tolerating surplus tokens in the candidate is therefore the point.

    The consequence is that a window containing the target *plus* unrelated lines also scores
    100, so score alone does not identify the right run. Among equally-scoring windows the
    shortest is the correct one: without that tie-break, matching picked the widest window
    and produced boxes spanning from the top of the label down to the real line (measured:
    a 211 px-tall box for a 21 px line), which would put a red evidence rectangle over six
    lines of a statutory notice.
    """
    needle = _normalise(target)
    if not needle:
        return None

    best: list[OcrWord] = []
    best_score = 0.0

    for start in range(len(words)):
        parts: list[str] = []
        for length in range(1, min(MAX_WINDOW, len(words) - start) + 1):
            parts.append(_normalise(words[start + length - 1].text))
            candidate = " ".join(p for p in parts if p)
            if not candidate:
                continue
            score = fuzz.token_set_ratio(needle, candidate)
            # Strictly better score, or the same score from a tighter window.
            if score > best_score or (score == best_score and best and length < len(best)):
                best_score = score
                best = words[start : start + length]

    if best_score < MATCH_THRESHOLD or not best:
        return None
    return best, best_score


def _cap_height_mm(window: list[OcrWord], scale: ScaleInfo) -> float:
    """Representative letter height for a matched declaration, in millimetres.

    Median, not minimum: a single mis-detected box would otherwise dominate and fabricate a
    font violation. Median across the words of the declaration is the robust estimate of how
    tall its lettering actually is.
    """
    heights = [w.cap_height_px for w in window if w.cap_height_px > 0]
    if not heights:
        return 0.0
    return round(statistics.median(heights) / scale.px_per_mm, 3)


def fuse(
    values: dict[DeclarationField, str],
    words: list[OcrWord],
    scale: ScaleInfo | None,
    base_confidence: float = 0.85,
) -> list[Declaration]:
    """Build Declarations by joining extracted values to OCR geometry.

    Declarations come back in `DeclarationField` order so the response — and therefore the
    notice and the UI list — is stable across runs on identical input.
    """
    ordered = _reading_order(words)
    declarations: list[Declaration] = []

    for declaration_field in DeclarationField:
        value = values.get(declaration_field)
        if not value:
            continue

        match = _best_window(value, ordered) if ordered else None
        if match is None:
            declarations.append(
                Declaration(
                    field=declaration_field,
                    value=value,
                    bbox=None,
                    confidence=round(base_confidence * 0.8, 3),  # unlocated: less to trust
                    geometry_source="none",
                )
            )
            continue

        window, score = match
        bbox = _union([w.bbox for w in window])
        # Blend the extraction prior with how well OCR corroborated it. Agreement between
        # two independent readers is genuine evidence; assert it, but modestly.
        ocr_confidence = statistics.mean(w.confidence for w in window)
        confidence = min(1.0, round((base_confidence + ocr_confidence * (score / 100.0)) / 2 + 0.05, 3))

        declarations.append(
            Declaration(
                field=declaration_field,
                value=value,
                bbox=bbox,
                confidence=confidence,
                geometry_source="ocr",
                text_height_mm=_cap_height_mm(window, scale) if scale else None,
            )
        )

    return declarations
