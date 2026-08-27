"""Declaration verification via Gemini, using PaddleOCR output as primary evidence.

Workflow:
  1. PaddleOCR runs first and produces word-level text + geometry.
  2. The OCR full-text is sent to Gemini together with the label image.
  3. Gemini's role is to VERIFY the OCR output:
     - Confirm or correct each declaration field from the OCR text.
     - Resolve OCR errors (0 vs O, 1 vs l, missing spaces) using the image.
     - Extract fields that OCR found but didn't structure (e.g. buried MRP).
     - Report null for fields that are genuinely absent.
  4. `fuse.py` then attaches precise OCR geometry to the verified values.

This separation is deliberate:
- OCR owns geometry (precise word polygons for font-height measurements).
- Gemini owns semantics (understanding which text is the MRP vs the weight).
- Neither alone is sufficient; both together produce trustworthy, measurable evidence.

With no GEMINI_API_KEY the module serves fixtures and flags EXTRACT_MOCKED.
The full pipeline (rules, notice) remains functional offline.
"""

from __future__ import annotations

import base64
import json
import logging
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.schemas import DeclarationField, DegradationFlag

logger = logging.getLogger(__name__)

GEMINI_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Field-by-field instructions. Kept beside the schema so a prompt change and a schema
# change cannot drift apart.
_FIELD_GUIDE = """\
- commodity_name: the name/description of the goods (e.g. "Refined Sunflower Oil").
- manufacturer_name: name of the manufacturer, packer, or importer.
- manufacturer_address: their full address as printed.
- net_quantity: the declared quantity WITH its unit, copied exactly as printed in the OCR
  text. If the OCR text says "500 gms", return "500 gms" — do not correct it to "500 g".
  This field is checked for non-standard unit symbols, so normalising it destroys the evidence.
- mrp: the retail sale price exactly as printed in the OCR text, including any currency
  symbol and any "inclusive of all taxes" wording that appears as part of the price.
- manufacture_date: date/month/year of manufacture or packing, as printed in the OCR text.
- best_before: "best before" or "use by" declaration, as printed.
- consumer_care: consumer-care contact — name, phone, email, or address for complaints.
- country_of_origin: country of origin or manufacture.
- fssai_number: FSSAI licence number if present.
"""

PROMPT_TEMPLATE = """\
You are assisting a Legal Metrology inspector in India. Your task is to VERIFY and STRUCTURE \
the text already extracted from a packaged-commodity label by an OCR engine.

The OCR engine has read the label and produced the following text (in approximate reading order):

--- OCR TEXT BEGIN ---
{ocr_text}
--- OCR TEXT END ---

The original label image is also provided so you can:
- Resolve characters the OCR engine commonly confuses (0/O, 1/l/I, rn/m, S/5).
- Read text the OCR engine missed or garbled beyond recognition.
- Confirm context (e.g. whether "145" is an MRP or a weight).

{field_guide}

Rules you must follow:
1. USE THE OCR TEXT AS YOUR PRIMARY SOURCE. Only override it when you can clearly see the \
correct character in the image. Do not re-read the whole label independently.
2. Transcribe EXACTLY as printed. Preserve spelling, abbreviations, unit symbols, and \
currency symbols verbatim in your output. The label's exact wording is legal evidence.
3. If a declaration is genuinely absent from BOTH the OCR text and the image, use null. \
Never guess or fill from general knowledge. A missing declaration is the violation being \
checked for — inventing one hides it.
4. `full_text` must be the corrected, complete text of the label. Start from the OCR text \
and correct obvious OCR errors you can verify from the image.
5. In `ocr_corrections`, list every word or value you changed from the OCR source, in the \
format "[OCR read] → [correct]" (e.g. "gms → g" is NOT a correction — that would alter \
evidence). Only list genuine OCR misreads (e.g. "O → 0" in a number, "Nashik" → "Nashk").
"""

# Gemini's responseSchema (OpenAPI subset). Enforcing the shape server-side means we
# never parse prose, and temperature 0 + a fixed schema keeps verification near-reproducible.
_RESPONSE_SCHEMA: dict[str, object] = {
    "type": "OBJECT",
    "properties": {
        **{f.value: {"type": "STRING", "nullable": True} for f in DeclarationField},
        "full_text": {"type": "STRING"},
        "ocr_corrections": {"type": "STRING", "nullable": True},
    },
    "required": ["full_text"],
}


@dataclass
class ExtractionResult:
    """Verification layer output: OCR text structured and corrected by Gemini."""

    values: dict[DeclarationField, str] = field(default_factory=dict)
    full_text: str = ""
    ocr_corrections: str = ""  # what Gemini changed from the OCR source
    # Per-field confidence. When Gemini agrees with OCR, trust is high.
    # When it overrides OCR, we inherit OCR's per-word confidence via fuse.py.
    confidence: float = 0.85
    degraded: list[DegradationFlag] = field(default_factory=list)


def _parse_payload(payload: dict) -> tuple[dict[DeclarationField, str], str, str]:
    parts = payload["candidates"][0]["content"]["parts"]
    text = "".join(p.get("text", "") for p in parts)
    data = json.loads(text)

    values: dict[DeclarationField, str] = {}
    for declaration in DeclarationField:
        raw = data.get(declaration.value)
        if raw is None:
            continue
        value = str(raw).strip()
        # A model that says "not present" instead of emitting null must not create a
        # phantom declaration — that would mask a genuine missing-declaration violation.
        if value and value.lower() not in {"null", "none", "n/a", "na", "not present", "-"}:
            values[declaration] = value

    corrections = str(data.get("ocr_corrections") or "").strip()
    return values, str(data.get("full_text", "")).strip(), corrections


def extract(image_png: bytes, ocr_text: str = "") -> ExtractionResult:
    """Verify and structure OCR-extracted text using Gemini.

    Gemini receives the PaddleOCR output as primary text evidence plus the label image
    for resolving ambiguous characters. It returns structured declaration values and
    a list of any OCR corrections it made.

    Never raises: on any failure the caller still gets an ExtractionResult carrying a
    degradation flag, so the pipeline reports honestly rather than 500-ing.
    """
    from app.fixtures import fixture_extraction

    settings = get_settings()
    if not settings.extraction_available:
        result = fixture_extraction()
        result.degraded = [DegradationFlag.EXTRACT_MOCKED]
        return result

    prompt = PROMPT_TEMPLATE.format(
        ocr_text=ocr_text if ocr_text.strip() else "(OCR produced no readable text)",
        field_guide=_FIELD_GUIDE,
    )

    body = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/png", "data": base64.b64encode(image_png).decode()}},
                ],
            }
        ],
        "generationConfig": {
            # Zero temperature is the closest we get to reproducible verification.
            # The determinism NFR is met strictly at the rules-engine boundary, not here.
            "temperature": 0.0,
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
        },
    }

    try:
        response = httpx.post(
            GEMINI_ENDPOINT.format(model=settings.gemini_model),
            headers={"x-goog-api-key": settings.gemini_api_key, "Content-Type": "application/json"},
            json=body,
            timeout=settings.gemini_timeout_s,
        )
        response.raise_for_status()
        values, full_text, ocr_corrections = _parse_payload(response.json())
    except httpx.HTTPStatusError as exc:
        logger.error("Gemini returned %s: %s", exc.response.status_code, exc.response.text[:400])
        # Fall back to raw OCR text so downstream rules can still run on what OCR found.
        return ExtractionResult(full_text=ocr_text, degraded=[DegradationFlag.EXTRACT_FAILED])
    except (httpx.HTTPError, KeyError, IndexError, ValueError) as exc:
        logger.error("Gemini verification failed: %s", exc)
        return ExtractionResult(full_text=ocr_text, degraded=[DegradationFlag.EXTRACT_FAILED])

    degraded: list[DegradationFlag] = []
    if not values:
        degraded.append(DegradationFlag.PARTIAL_TEXT)

    # Prefer Gemini's corrected full_text over the raw OCR text: it has the same content
    # but with character-level OCR errors resolved. If Gemini returned less than the OCR
    # text, that's a truncation — keep OCR in that case.
    if len(ocr_text) > len(full_text) * 1.2:
        full_text = ocr_text

    if ocr_corrections:
        logger.info("Gemini OCR corrections: %s", ocr_corrections)

    return ExtractionResult(
        values=values,
        full_text=full_text,
        ocr_corrections=ocr_corrections,
        degraded=degraded,
    )
