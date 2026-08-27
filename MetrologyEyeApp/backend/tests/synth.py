"""Synthetic label generation for tests.

Rendering our own labels — including a genuinely decodable EAN-13 — means the scale and
OCR paths can be tested without checking photographs into the repo and without a test
suite that depends on someone's phone camera.

The EAN-13 encoder is real, not a stripe pattern: `cv2.barcode.BarcodeDetector` validates
the checksum, so a fake would be detected-but-not-decoded and `test_scale` would silently
assert the weaker of the two confidence paths.
"""

from __future__ import annotations

import cv2
import numpy as np

# ISO/IEC 15420 element patterns. Left digits use set A or B per the parity table; right
# digits always use set C.
_SET_A = ("0001101", "0011001", "0010011", "0111101", "0100011",
          "0110001", "0101111", "0111011", "0110111", "0001011")
_SET_B = ("0100111", "0110011", "0011011", "0100001", "0011101",
          "0111001", "0000101", "0010001", "0001001", "0010111")
_SET_C = ("1110010", "1100110", "1101100", "1000010", "1011100",
          "1001110", "1010000", "1000100", "1001000", "1110100")

# Which of digits 2-7 use set B, selected by the first digit.
_PARITY = ("AAAAAA", "AABABB", "AABBAB", "AABBBA", "ABAABB",
           "ABBAAB", "ABBBAA", "ABABAB", "ABABBA", "ABBABA")

QUIET_MODULES = 9  # quiet zone each side, in modules
SYMBOL_MODULES = 95  # 3 + 42 + 5 + 42 + 3


def ean13_checksum(twelve: str) -> int:
    digits = [int(c) for c in twelve]
    return (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits)) % 10) % 10


def ean13_modules(code: str) -> str:
    """Encode a 12- or 13-digit code to its 95-module bit string."""
    if len(code) == 12:
        code += str(ean13_checksum(code))
    if len(code) != 13 or not code.isdigit():
        raise ValueError("EAN-13 requires 12 or 13 digits")

    parity = _PARITY[int(code[0])]
    bits = "101"
    for index, char in enumerate(code[1:7]):
        bits += (_SET_A if parity[index] == "A" else _SET_B)[int(char)]
    bits += "01010"
    for char in code[7:]:
        bits += _SET_C[int(char)]
    return bits + "101"


def render_ean13(code: str, module_px: int = 3, height_px: int = 90) -> np.ndarray:
    """Render an EAN-13 symbol including quiet zones, as a white-background BGR image.

    Returns an image whose *symbol* (excluding quiet zones) is
    `SYMBOL_MODULES * module_px` wide — the width `scale.py` should measure.
    """
    bits = ean13_modules(code)
    total_modules = SYMBOL_MODULES + 2 * QUIET_MODULES
    image = np.full((height_px, total_modules * module_px, 3), 255, np.uint8)
    for index, bit in enumerate(bits):
        if bit == "1":
            x = (QUIET_MODULES + index) * module_px
            image[:, x : x + module_px] = 0
    return image


def render_label(
    lines: list[tuple[str, float]],
    barcode: str | None = "8901234567890",
    module_px: int = 3,
    width: int = 900,
    soften: int = 3,
) -> np.ndarray:
    """Render a label: text lines as (text, font_scale), plus an optional barcode.

    `soften` applies a mild Gaussian blur, on by default: no printer or camera produces
    perfect square-wave edges, and a pixel-perfect render is *less* representative of a
    real photograph than a slightly soft one. It also keeps the synthetic barcode within
    the range OpenCV's gradient-based detector can see — see `scale._BLUR_KERNELS`.

    Returns BGR. Encode with `cv2.imencode('.png', ...)` to feed the API or pipeline.
    """
    barcode_image = render_ean13(barcode, module_px=module_px) if barcode else None
    barcode_h = barcode_image.shape[0] + 30 if barcode_image is not None else 0

    line_h = 46
    height = 40 + line_h * len(lines) + barcode_h + 30
    image = np.full((height, width, 3), 255, np.uint8)

    y = 50
    for text, font_scale in lines:
        cv2.putText(
            image, text, (30, y), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (10, 10, 10), 2, cv2.LINE_AA
        )
        y += line_h

    if barcode_image is not None:
        bh, bw = barcode_image.shape[:2]
        y += 15
        image[y : y + bh, 30 : 30 + bw] = barcode_image

    if soften:
        image = cv2.GaussianBlur(image, (soften, soften), 0)
    return image


def png_bytes(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok, "failed to encode synthetic label"
    return encoded.tobytes()


# A label with three deliberate defects: 'gms' (non-standard unit), an MRP with no
# tax-inclusive wording, and no country of origin.
NONCOMPLIANT_LINES: list[tuple[str, float]] = [
    ("SURAJ REFINED SUNFLOWER OIL", 0.9),
    ("Net Quantity: 500 gms", 0.8),
    ("MRP Rs. 145.00", 0.8),
    ("Mfd: 03/2026", 0.8),
    ("Mfd by Suraj Foods Private Limited,", 0.6),
    ("Plot 14, MIDC Area, Nashik, Maharashtra 422007", 0.55),
    ("Consumer care: care@surajfoods.example", 0.55),
]

COMPLIANT_LINES: list[tuple[str, float]] = [
    ("SURAJ REFINED SUNFLOWER OIL", 0.9),
    ("Net Quantity: 500 g", 0.8),
    ("MRP Rs. 145.00 (inclusive of all taxes)", 0.7),
    ("Mfd: 03/2026", 0.8),
    ("Country of Origin: India", 0.7),
    ("Mfd by Suraj Foods Private Limited,", 0.6),
    ("Plot 14, MIDC Area, Nashik, Maharashtra 422007", 0.55),
    ("Consumer care: care@surajfoods.example", 0.55),
]
