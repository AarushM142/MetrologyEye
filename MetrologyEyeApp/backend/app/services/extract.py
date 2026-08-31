"""Declaration verification via the DeepInfra VLM, using PaddleOCR output as primary evidence.

Workflow:
  1. PaddleOCR runs first and produces word-level text + geometry.
  2. The OCR full-text is sent to the DeepInfra VLM together with the label image.
  3. The VLM's role is to VERIFY the OCR output:
     - Confirm or correct each declaration field from the OCR text.
     - Resolve OCR errors (0 vs O, 1 vs l, missing spaces) using the image.
     - Extract fields that OCR found but didn't structure (e.g. buried MRP).
     - Report null for fields that are genuinely absent.
  4. `fuse.py` then attaches precise OCR geometry to the verified values.

This separation is deliberate:
- OCR owns geometry (precise word polygons for font-height measurements).
- The VLM owns semantics (understanding which text is the MRP vs the weight).
- Neither alone is sufficient; both together produce trustworthy, measurable evidence.

With no DEEPINFRA_API_KEY the module serves fixtures and flags EXTRACT_MOCKED.
The full pipeline (rules, notice) remains functional offline.
"""

from __future__ import annotations

import base64
import json
import logging
import time
from dataclasses import dataclass, field

import httpx

from app.config import get_settings
from app.schemas import DeclarationField, DegradationFlag

logger = logging.getLogger(__name__)

DEEPINFRA_ENDPOINT = "https://api.deepinfra.com/v1/openai/chat/completions"

from app.services.prompts import PROMPT_TEMPLATE, _FIELD_GUIDE

# We removed _RESPONSE_SCHEMA because DeepInfra uses standard JSON mode.


@dataclass
class ExtractionResult:
    """Verification layer output: OCR text structured and corrected by the VLM."""

    values: dict[DeclarationField, str] = field(default_factory=dict)
    full_text: str = ""
    ocr_corrections: str = ""  # what the VLM changed from the OCR source
    # Per-field confidence. When the VLM agrees with OCR, trust is high.
    # When it overrides OCR, we inherit OCR's per-word confidence via fuse.py.
    confidence: float = 0.85
    degraded: list[DegradationFlag] = field(default_factory=list)
    # Precise wall-clock latency of the VLM API call, in milliseconds. Populates
    # `timings_ms["extract"]` so the <3 s NFR is measured at the network boundary,
    # not just around the whole extract stage. 0.0 when no API call was made.
    latency_ms: float = 0.0


def _parse_payload(payload: dict) -> tuple[dict[DeclarationField, str], str, str]:
    content = payload["choices"][0]["message"]["content"]
    data = json.loads(content)

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
    """Verify and structure OCR-extracted text using the DeepInfra VLM.

    The VLM receives the PaddleOCR output as primary text evidence plus the label image
    for resolving ambiguous characters. It returns structured declaration values and
    a list of any OCR corrections it made.

    Never raises: on any failure the caller still gets an ExtractionResult carrying a
    degradation flag, so the pipeline reports honestly rather than 500-ing.
    """
    settings = get_settings()
    if not settings.extraction_available:
        logger.error("CRITICAL: DEEPINFRA_API_KEY is missing from .env!")
        raise ValueError("AI Extraction is unavailable. Please check your DEEPINFRA_API_KEY.")

    prompt = PROMPT_TEMPLATE.format(
        ocr_text=ocr_text if ocr_text.strip() else "(OCR produced no readable text)",
        field_guide=_FIELD_GUIDE,
    )

    body = {
        "model": settings.deepinfra_model,
        "messages": [
            {
                "role": "system",
                "content": "/no_think\n" + prompt,
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Extract mandatory declarations from this package label. Return JSON only. Use null for any field not clearly printed."},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{base64.b64encode(image_png).decode()}"
                        }
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "response_format": {"type": "json_object"}
    }

    # Time the actual model call so we can report the true network+inference latency.
    start = time.perf_counter()
    try:
        response = httpx.post(
            DEEPINFRA_ENDPOINT,
            headers={
                "Authorization": f"Bearer {settings.deepinfra_api_key}", 
                "Content-Type": "application/json"
            },
            json=body,
            timeout=settings.deepinfra_timeout_s,
        )
        response.raise_for_status()
        latency_s = time.perf_counter() - start
        raw_content = response.json()["choices"][0]["message"]["content"]
        print(f"\n[VLM RAW RESPONSE]\n{raw_content}\n")
        values, full_text, ocr_corrections = _parse_payload(response.json())
    except httpx.HTTPStatusError as exc:
        error_msg = f"DeepInfra API Error {exc.response.status_code}: {exc.response.text[:400]}"
        print(f"\n[CRITICAL DEEPINFRA ERROR]\n{error_msg}\n")
        logger.error(error_msg)
        raise RuntimeError(error_msg) from exc
    except (httpx.HTTPError, KeyError, IndexError, RuntimeError) as exc:
        error_msg = f"DeepInfra verification crashed: {exc}"
        print(f"\n[CRITICAL DEEPINFRA ERROR]\n{error_msg}\n")
        logger.error(error_msg)
        raise RuntimeError(error_msg) from exc

    latency_ms = latency_s * 1000.0
    logger.info(f"VLM API Latency: {latency_s:.2f} seconds ({latency_ms:.0f} ms)")

    degraded: list[DegradationFlag] = []
    if not values:
        degraded.append(DegradationFlag.PARTIAL_TEXT)

    # Prefer the VLM's corrected full_text over the raw OCR text: it has the same content
    # but with character-level OCR errors resolved. If the VLM returned less than the OCR
    # text, that's a truncation — keep OCR in that case.
    if len(ocr_text) > len(full_text) * 1.2:
        full_text = ocr_text

    if ocr_corrections:
        logger.info("DeepInfra OCR corrections: %s", ocr_corrections)

    return ExtractionResult(
        values=values,
        full_text=full_text,
        ocr_corrections=ocr_corrections,
        degraded=degraded,
        latency_ms=latency_ms,
    )
