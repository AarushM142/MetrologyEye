"""Word-level OCR via PaddleOCR.

OCR exists here for one reason: **geometry**. Gemini reads the label far better than any
OCR engine, but its bounding boxes are approximate, and we need boxes precise enough to
measure a letter against a statutory millimetre minimum. So PaddleOCR supplies exact word
polygons and `fuse.py` attaches them to the values Gemini extracted.

PaddleOCR is imported lazily and behind a cache. A missing or broken install degrades the
run to `OCR_UNAVAILABLE` (no boxes, no font checks) instead of failing the request.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache

import numpy as np

from app.schemas import BBox

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OcrWord:
    """One recognised text run with its polygon.

    `cap_height_px` is the quantity the font-size rule actually needs, and it is not the
    same as the box height: PaddleOCR boxes include descenders and padding. See
    `_cap_height` for the correction and its limits.
    """

    text: str
    bbox: BBox
    confidence: float
    cap_height_px: float


@lru_cache(maxsize=1)
def _engine() -> object | None:
    """Build the PaddleOCR engine once. Returns None if unavailable.

    First call downloads detection/recognition weights (~10 MB) and takes several
    seconds; subsequent calls are fast. Warm this at startup before a live demo.
    """
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:  # ImportError, or a paddle DLL failure on Windows
        logger.warning("PaddleOCR unavailable (%s); geometry will be VLM-only.", exc)
        return None

    try:
        return PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
    except Exception as exc:  # pragma: no cover - model download / init failure
        logger.warning("PaddleOCR failed to initialise (%s).", exc)
        return None


def ocr_available() -> bool:
    """Whether OCR is wired. Surfaced by /health so a demo operator knows before starting."""
    return _engine() is not None


def _cap_height(polygon: np.ndarray, text: str) -> float:
    """Estimate cap height in pixels from a word polygon.

    PaddleOCR's box spans ascender to descender plus a little padding. Legal Metrology
    specifies letter height, so we scale the box height down when the text contains
    descenders and leave it alone otherwise. This is an approximation — which is one more
    reason font findings are warnings, not violations.
    """
    ys = polygon[:, 1]
    box_height = float(ys.max() - ys.min())
    if box_height <= 0:
        return 0.0
    has_descender = any(c in "gjpqy" for c in text)
    has_ascender = any(c.isupper() or c.isdigit() or c in "bdfhklt" for c in text)
    if has_descender and has_ascender:
        return box_height * 0.72  # full ascender-to-descender span
    if has_descender:
        return box_height * 0.62  # x-height plus descender
    return box_height * 0.90  # ascenders only, minus padding


def _to_bbox(polygon: np.ndarray) -> BBox:
    xs, ys = polygon[:, 0], polygon[:, 1]
    x, y = int(xs.min()), int(ys.min())
    return (x, y, int(xs.max()) - x, int(ys.max()) - y)


def _is_line(item: object) -> bool:
    """Whether `item` is a PaddleOCR line: [polygon, (text, confidence)].

    Shape-sniffing on the payload rather than on nesting depth. A depth test is wrong for
    the single-detection case — a flat `[[poly, (text, conf)]]` and a page-wrapped
    `[[[poly, (text, conf)]]]` are indistinguishable by depth, so unwrapping one as the
    other silently reinterprets a polygon as a line and drops the only text on the label.
    """
    if not isinstance(item, (list, tuple)) or len(item) < 2:
        return False
    payload = item[1]
    return isinstance(payload, (list, tuple)) and len(payload) >= 2 and isinstance(payload[0], str)


def _normalise_result(raw: object) -> list[tuple[np.ndarray, str, float]]:
    """Flatten PaddleOCR output into (polygon, text, confidence) triples.

    PaddleOCR's return shape has changed across 2.x releases: some versions wrap the page
    list one level deeper than others, and 2.9 yields `[None]` when nothing is detected.
    So walk the structure looking for line-shaped nodes instead of assuming a fixed depth.
    """
    out: list[tuple[np.ndarray, str, float]] = []

    def walk(node: object, depth: int = 0) -> None:
        if node is None or depth > 4:
            return
        if _is_line(node):
            polygon, payload = node[0], node[1]  # type: ignore[index]
            try:
                out.append(
                    (np.asarray(polygon, dtype=np.float64), str(payload[0]), float(payload[1]))
                )
            except (TypeError, ValueError):
                pass
            return
        if isinstance(node, (list, tuple)):
            for child in node:
                walk(child, depth + 1)

    walk(raw)
    return out


def read_words(image: np.ndarray) -> list[OcrWord]:
    """Run OCR. Returns [] when OCR is unavailable or finds nothing — never raises."""
    engine = _engine()
    if engine is None:
        return []

    try:
        raw = engine.ocr(image, cls=True)
    except Exception as exc:  # pragma: no cover - runtime inference failure
        logger.warning("OCR inference failed (%s).", exc)
        return []

    words: list[OcrWord] = []
    for polygon, text, confidence in _normalise_result(raw):
        text = text.strip()
        if not text or polygon.shape[0] < 4:
            continue
        words.append(
            OcrWord(
                text=text,
                bbox=_to_bbox(polygon),
                confidence=confidence,
                cap_height_px=_cap_height(polygon, text),
            )
        )
    return words


def full_text(words: list[OcrWord]) -> str:
    """Reading-order concatenation of OCR text.

    Rules that test for a *phrase* rather than a field — "inclusive of all taxes" is the
    case that matters — search this, because such phrases sit next to the MRP rather than
    inside any single extracted declaration.
    """
    # Sort by row band before column so multi-column labels read sanely. The 12 px band
    # tolerates baseline jitter without merging distinct lines.
    ordered = sorted(words, key=lambda w: (w.bbox[1] // 12, w.bbox[0]))
    return " ".join(w.text for w in ordered)
