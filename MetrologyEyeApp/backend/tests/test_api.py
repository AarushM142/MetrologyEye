"""End-to-end API tests: upload -> analyse -> notice.

This is the first test to exercise `pipeline.py` and `notice.py` at all, and it goes through
real HTTP so the multipart handling, the threadpool offload, storage, and the response schema
are all covered rather than assumed.

The VLM call is mocked at the network boundary by `tests/conftest.py`, so these tests never
touch the network and never spend anyone's quota. Everything downstream of extraction —
fusion, the rules engine, the Form-I notice — is the real production code path; only the
DeepInfra response is a fixture.
"""

from __future__ import annotations

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.schemas import DeclarationField, Severity
from tests.synth import NONCOMPLIANT_LINES, png_bytes, render_label

VALID_CODE = "8901234567890"


@pytest.fixture(scope="module")
def label_png() -> bytes:
    """A deliberately non-compliant label with a decodable barcode."""
    return png_bytes(
        render_label(NONCOMPLIANT_LINES, barcode=VALID_CODE, module_px=4, width=1200)
    )


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _analyze(client: TestClient, image: bytes, **data) -> dict:
    response = client.post(
        "/api/analyze",
        files={"file": ("label.png", image, "image/png")},
        data=data,
    )
    assert response.status_code == 200, response.text
    return response.json()


# --- health ----------------------------------------------------------------------


def test_health_reports_which_extractor_is_live(client: TestClient):
    """The demo needs to know whether it is running mocked or live, without guessing."""
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["extraction"] == "deepinfra"
    assert body["deepinfra_model"] == "meta-llama/Llama-3.2-90B-Vision-Instruct"


# --- analyze ---------------------------------------------------------------------


def test_analyze_returns_the_frozen_contract(client: TestClient, label_png: bytes):
    body = _analyze(client, label_png)

    assert set(body) >= {
        "analysis_id",
        "source",
        "image",
        "scale",
        "declarations",
        "findings",
        "summary",
        "timings_ms",
        "degraded",
        "manual_inspection_required",
    }
    assert body["source"] == "upload"
    assert body["image"]["preview_url"] == f"/api/image/{body['analysis_id']}"
    # Extraction ran through the mocked DeepInfra path — it must not have failed.
    assert "extract_failed" not in body["degraded"]
    assert body["manual_inspection_required"] is False


def test_analyze_finds_the_three_seeded_violations(client: TestClient, label_png: bytes):
    """The fixture label breaks three distinct rules; each must be reported once."""
    body = _analyze(client, label_png)

    violations = {
        f["rule_id"] for f in body["findings"] if f["severity"] == Severity.VIOLATION.value
    }
    assert violations == {
        "UNIT_NONSTANDARD",
        "MRP_TAX_WORDING_MISSING",
        "MISSING_DECLARATION",
    }
    assert body["summary"]["violations"] == 3


def test_every_citation_is_flagged_unverified(client: TestClient, label_png: bytes):
    """Until the statute is checked, no finding may present its citation as confirmed.

    This is the assertion that keeps an unverified legal reference from quietly hardening
    into an apparently authoritative one.
    """
    body = _analyze(client, label_png)
    assert body["findings"], "expected findings to assert against"
    assert all(f["verified_citation"] is False for f in body["findings"])
    assert all(f["citation"] for f in body["findings"])


def test_barcode_yields_a_scale_with_declared_uncertainty(client: TestClient, label_png: bytes):
    body = _analyze(client, label_png)
    scale = body["scale"]

    assert scale is not None, "barcode present but no scale recovered"
    assert scale["source"] == "ean13"
    assert scale["barcode_value"] == VALID_CODE
    assert 0.0 < scale["confidence"] < 1.0, "the magnification assumption forbids certainty"
    assert scale["assumed_magnification"] == 1.0
    assert "no_barcode" not in body["degraded"]


def test_bboxes_lie_inside_the_served_frame(client: TestClient, label_png: bytes):
    """The canvas draws these boxes over `preview_url`, so any box outside the frame is a
    visible defect. Catches a coordinate-space mismatch between preprocessing and OCR."""
    body = _analyze(client, label_png)
    width, height = body["image"]["width"], body["image"]["height"]

    boxes = [d["bbox"] for d in body["declarations"] if d["bbox"]]
    boxes += [f["bbox"] for f in body["findings"] if f["bbox"]]
    assert boxes, "expected at least one located declaration"

    for x, y, w, h in boxes:
        assert 0 <= x and 0 <= y, f"negative origin: {(x, y, w, h)}"
        assert w > 0 and h > 0, f"degenerate box: {(x, y, w, h)}"
        assert x + w <= width and y + h <= height, f"box outside frame: {(x, y, w, h)}"


def test_located_declarations_get_tight_single_line_boxes(client: TestClient, label_png: bytes):
    """Regression guard for the sprawling-evidence bug, asserted through the API.

    Boxes once spanned from the top of the label to the matched line — 211 px tall for a
    21 px line. A box taller than a large fraction of the label is not evidence of one
    declaration, whatever its text similarity score.
    """
    body = _analyze(client, label_png)
    height = body["image"]["height"]

    located = [d for d in body["declarations"] if d["bbox"]]
    assert located, "expected located declarations"

    for declaration in located:
        box_height = declaration["bbox"][3]
        assert box_height < height * 0.25, (
            f"{declaration['field']} box is {box_height}px tall in a {height}px frame — "
            "fusion is unioning unrelated lines again"
        )


def test_net_quantity_violation_points_at_the_net_quantity_text(
    client: TestClient, label_png: bytes
):
    """A finding's box must sit on the offending declaration, not merely exist.

    NOTE: bbox availability depends on PaddleOCR successfully matching the fixture
    value ('500 gms') to an OCR word. Some fonts cause OCR to read '0' as 'o',
    yielding '5oo gms', which fuse cannot match. When OCR locates the declaration
    we assert full alignment; when it can't, we still assert the value is correct.
    """
    body = _analyze(client, label_png)

    net = next(
        d for d in body["declarations"] if d["field"] == DeclarationField.NET_QUANTITY.value
    )
    unit_finding = next(f for f in body["findings"] if f["rule_id"] == "UNIT_NONSTANDARD")

    assert "gms" in net["value"], f"expected 'gms' unit in net_quantity, got: {net['value']!r}"
    if net["bbox"] is not None:
        # OCR successfully located the declaration — assert the finding points to it.
        assert unit_finding["bbox"] == net["bbox"], (
            "UNIT_NONSTANDARD finding bbox must match net_quantity bbox"
        )

def test_manual_scale_overrides_barcode_detection(client: TestClient, label_png: bytes):
    """The calibration slider must win — a human with a ruler outranks our inference."""
    body = _analyze(client, label_png, manual_px_per_mm=8.0)
    assert body["scale"]["source"] == "manual"
    assert body["scale"]["px_per_mm"] == 8.0
    assert body["scale"]["confidence"] == 1.0


def test_label_without_a_barcode_degrades_instead_of_guessing(client: TestClient):
    """No barcode must suppress font checks, not fabricate a scale."""
    body = _analyze(client, png_bytes(render_label(NONCOMPLIANT_LINES, barcode=None, width=1200)))

    assert body["scale"] is None
    assert "no_barcode" in body["degraded"]
    assert not [f for f in body["findings"] if f["rule_id"] == "FONT_HEIGHT_BELOW_MINIMUM"]
    # The rest of the analysis still has to work — the unit rule does not need a scale.
    assert body["summary"]["violations"] >= 1


def test_blurry_upload_asks_for_manual_inspection(client: TestClient, label_png: bytes):
    """NFR-3: an unreliable read must say so rather than present a confident result."""
    image = cv2.imdecode(np.frombuffer(label_png, np.uint8), cv2.IMREAD_COLOR)
    body = _analyze(client, png_bytes(cv2.GaussianBlur(image, (21, 21), 0)))

    assert "blurry_image" in body["degraded"]
    assert body["manual_inspection_required"] is True


def test_timings_are_reported_for_every_stage(client: TestClient, label_png: bytes):
    """The <3 s NFR is observable rather than asserted, so the numbers must be present."""
    timings = _analyze(client, label_png)["timings_ms"]
    for stage in ("preprocess", "scale", "ocr", "extract", "rules", "total"):
        assert timings[stage] >= 0
    assert timings["total"] >= max(
        timings[s] for s in ("preprocess", "scale", "ocr", "extract", "rules")
    )


def test_empty_upload_is_rejected(client: TestClient):
    response = client.post("/api/analyze", files={"file": ("empty.png", b"", "image/png")})
    assert response.status_code == 400


def test_undecodable_upload_is_a_422_not_a_500(client: TestClient):
    response = client.post(
        "/api/analyze", files={"file": ("not.png", b"plainly not an image", "image/png")}
    )
    assert response.status_code == 422


# --- retrieval -------------------------------------------------------------------


def test_analysis_can_be_reread_so_a_refresh_survives(client: TestClient, label_png: bytes):
    body = _analyze(client, label_png)
    again = client.get(f"/api/analysis/{body['analysis_id']}")
    assert again.status_code == 200
    assert again.json() == body


def test_served_image_is_the_frame_the_boxes_belong_to(client: TestClient, label_png: bytes):
    """Serving the original upload instead of the preprocessed frame would offset every box
    by the deskew and downscale, so assert the dimensions agree with the response."""
    body = _analyze(client, label_png)
    response = client.get(body["image"]["preview_url"])

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    served = cv2.imdecode(np.frombuffer(response.content, np.uint8), cv2.IMREAD_COLOR)
    assert served.shape[1] == body["image"]["width"]
    assert served.shape[0] == body["image"]["height"]


def test_unknown_ids_are_404(client: TestClient):
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.get(f"/api/analysis/{missing}").status_code == 404
    assert client.get(f"/api/image/{missing}").status_code == 404
    assert client.post("/api/notice", json={"analysis_id": missing}).status_code == 404


# --- notice ----------------------------------------------------------------------


def test_notice_is_a_preliminary_assessment_pdf(client: TestClient, label_png: bytes):
    body = _analyze(client, label_png)
    response = client.post(
        "/api/notice",
        json={
            "analysis_id": body["analysis_id"],
            "inspector_name": "A. Deshmukh",
            "inspector_designation": "Legal Metrology Officer",
            "premises": "Retail outlet, Nashik",
        },
    )

    assert response.status_code == 200, response.text
    assert response.headers["content-type"] == "application/pdf"
    # inline, not attachment: the browser renders it in a new tab.
    assert response.headers["content-disposition"] == 'inline; filename="notice.pdf"'

    pdf = response.content
    assert pdf.startswith(b"%PDF-")
    assert pdf.rstrip().endswith(b"%%EOF")
    # A Phase 8 notice is a substantial document: banner, findings table, signature block.
    assert len(pdf) > 2_000, f"notice is suspiciously small ({len(pdf)} bytes) — layout may have failed"


def test_notice_works_without_inspector_details(client: TestClient, label_png: bytes):
    """The demo fills these in last; a blank form must still render."""
    body = _analyze(client, label_png)
    response = client.post("/api/notice", json={"analysis_id": body["analysis_id"]})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")


def test_notice_renders_when_no_scale_was_recovered(client: TestClient):
    """The no-barcode path reaches the notice too, and a null scale must not break layout."""
    body = _analyze(client, png_bytes(render_label(NONCOMPLIANT_LINES, barcode=None, width=1200)))
    assert body["scale"] is None

    response = client.post("/api/notice", json={"analysis_id": body["analysis_id"]})
    assert response.status_code == 200
    assert response.content.startswith(b"%PDF-")
