"""HTTP routes.

Deliberately thin — validation, delegation, storage, response. No CV or statutory logic
lives here, so the pipeline stays testable without an HTTP client.

The pipeline is CPU-bound (OpenCV, OCR) and blocking, so every analyze route hands it to
`run_in_threadpool`. Calling it directly from an `async def` would stall the event loop and
make concurrent requests queue behind each other for seconds at a time.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import Response
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.schemas import AnalyzeResponse, NoticeRequest, NoticeReviewRequest, UrlIngestRequest
from app.services import ingest, notice, pipeline, storage
from app.store import store

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analysis"])

_ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png", "image/webp", "image/bmp", "image/heic"}


def _validate_upload(file: UploadFile, data: bytes) -> None:
    limit_mb = get_settings().max_upload_mb
    if not data:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "The uploaded file was empty.")
    if len(data) > limit_mb * 1024 * 1024:
        raise HTTPException(
            status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            f"Image is larger than {limit_mb} MB. Reduce the resolution and retry.",
        )
    # Content type is advisory only — browsers mislabel HEIC and some send
    # application/octet-stream. The real gate is whether OpenCV can decode it, which
    # preprocess.decode() enforces.
    if file.content_type and file.content_type not in _ALLOWED_IMAGE_TYPES:
        logger.info("Unexpected content-type %s; attempting decode anyway.", file.content_type)


async def _run(image_bytes: bytes, source: str, manual_px_per_mm: float | None) -> AnalyzeResponse:
    try:
        analysis, preview_png = await run_in_threadpool(
            pipeline.analyze, image_bytes, source, manual_px_per_mm
        )
    except ValueError as exc:  # undecodable image
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
    except Exception as exc:  # pragma: no cover - unexpected pipeline failure
        logger.exception("Analysis failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Analysis failed: {exc}"
        ) from exc

    store.put(analysis, preview_png)

    # Phase 7: persist the analysis to local disk before returning. Writes are atomic and
    # the directory is auto-created, so this is the durable audit trail behind the notice.
    storage.save_analysis(analysis)

    return analysis


@router.post("/analyze", response_model=AnalyzeResponse)
async def analyze_upload(
    file: UploadFile = File(..., description="Label photograph"),
    manual_px_per_mm: float | None = Form(
        default=None,
        gt=0,
        description="Operator-supplied scale from the calibration slider. Overrides barcode "
        "detection and is trusted at full confidence.",
    ),
) -> AnalyzeResponse:
    """Analyse an uploaded label image."""
    data = await file.read()
    _validate_upload(file, data)
    return await _run(data, "upload", manual_px_per_mm)


@router.post("/analyze/url", response_model=AnalyzeResponse)
async def analyze_url(request: UrlIngestRequest) -> AnalyzeResponse:
    """Analyse the primary product image from an e-commerce listing URL.

    Separate from `/analyze` rather than one overloaded endpoint: multipart and JSON bodies
    do not coexist cleanly, and the failure modes are entirely different — a bad upload is a
    decode problem, a bad URL is a network or scraping problem worth its own message.
    """
    try:
        image_bytes = await run_in_threadpool(ingest.fetch_image, request.url)
    except ingest.IngestError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return await _run(image_bytes, "url", None)


@router.get("/analysis/{analysis_id}", response_model=AnalyzeResponse)
def get_analysis(analysis_id: str) -> AnalyzeResponse:
    """Re-read a persisted analysis from disk, so the results page survives a restart."""
    analysis = storage.load_analysis(analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")
    return analysis


@router.get(
    "/image/{analysis_id}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
)
def get_image(analysis_id: str) -> Response:
    """Serve the preprocessed frame.

    This is the *preprocessed* image, not the original upload, and that matters: every bbox
    in the response is in this frame's coordinate space. Serving the original would offset
    every box the canvas draws by the deskew and downscale.
    """
    image_png = store.get_image(analysis_id)
    if image_png is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Image not found or expired.")
    return Response(
        content=image_png,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.post("/notice", response_class=Response, responses={200: {"content": {"application/pdf": {}}}})
async def create_notice(request: NoticeRequest) -> Response:
    """Generate the Form-I inspection notice PDF from the persisted analysis."""
    analysis = storage.load_analysis(request.analysis_id)
    if analysis is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")

    try:
        pdf = await run_in_threadpool(
            notice.build_notice, analysis.model_dump(mode="json"), request
        )
    except Exception as exc:  # pragma: no cover - ReportLab layout failure
        logger.exception("Notice generation failed")
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, f"Could not generate notice: {exc}"
        ) from exc

    return Response(
        content=pdf,
        media_type="application/pdf",
        # inline: the browser renders the PDF in a new tab rather than downloading it.
        headers={"Content-Disposition": 'inline; filename="notice.pdf"'},
    )


@router.patch("/notice/{notice_id}/review")
def review_notice(notice_id: str, request: NoticeReviewRequest) -> dict[str, str]:
    """Record a reviewer and reviewed_at timestamp on a persisted analysis.

    Auth is stubbed: `reviewer_id` is an opaque string for now. In this local MVP the
    notice is represented by its analysis record, so the review is stamped onto
    `{analysis_id}.json` (the id in the URL is the analysis id).
    """
    if not storage.update_notice_review(notice_id, request.reviewer_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Analysis not found.")
    return {"id": notice_id, "reviewer_id": request.reviewer_id, "status": "reviewed"}
