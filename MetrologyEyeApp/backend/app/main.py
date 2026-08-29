"""FastAPI application entrypoint.

    cd backend
    .venv/Scripts/python -m uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title="MetrologyEye API",
    version="0.1.0",
    description=(
        "Automated Legal Metrology compliance checking for packaged commodity labels "
        "(SIH26034). Extracts mandatory declarations from a label image, validates them "
        "against the LMPC Rules 2011, and generates a Form-I inspection notice."
    ),
)

app.add_middleware(
    CORSMiddleware,
    # Explicit origin, not "*" — credentials-bearing requests are rejected against a
    # wildcard, and the frontend origin is known.
    allow_origins=[settings.cors_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health", tags=["meta"])
def health() -> dict[str, object]:
    """Liveness plus a readout of which optional capabilities are actually wired.

    Returned in the response rather than logged so the demo operator can see, before
    presenting, whether extraction will be real or mocked.
    """
    from app.services.ocr import ocr_available

    return {
        "status": "ok",
        "extraction": "deepinfra" if settings.extraction_available else "mocked",
        "deepinfra_model": settings.deepinfra_model if settings.extraction_available else None,
        "ocr": "paddleocr" if ocr_available() else "unavailable",
        "persistence": "local-filesystem",
    }
