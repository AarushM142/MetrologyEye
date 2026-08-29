"""Local file-based persistence (Phase 7, revised).

Zero-dependency local store: every analysis is written as a JSON file to
`backend/data/analyses/{analysis_id}.json`. This keeps the audit trail and the
notice-review state without a database or external service.

Layout:
    backend/data/analyses/<analysis_id>.json   # full AnalyzeResponse payload

The directory is created on first use. Writes go through a temp-file-then-rename so a
crash mid-write cannot leave a half-written analysis.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from app.config import BACKEND_ROOT
from app.schemas import AnalyzeResponse

logger = logging.getLogger(__name__)

DATA_DIR = BACKEND_ROOT / "data"
ANALYSES_DIR = DATA_DIR / "analyses"


def _ensure_dir() -> Path:
    ANALYSES_DIR.mkdir(parents=True, exist_ok=True)
    return ANALYSES_DIR


def _path(analysis_id: str) -> Path:
    return _ensure_dir() / f"{analysis_id}.json"


def _write_text_atomic(path: Path, text: str) -> None:
    """Write `text` to `path` atomically (temp file + rename)."""
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def save_analysis(analysis: AnalyzeResponse) -> Path:
    """Persist the full analysis payload as JSON. Returns the file path."""
    path = _path(analysis.analysis_id)
    _write_text_atomic(path, analysis.model_dump_json(indent=2))
    logger.info("analysis %s saved to %s", analysis.analysis_id, path)
    return path


def load_analysis(analysis_id: str) -> AnalyzeResponse | None:
    """Read a persisted analysis, or None when no such file exists."""
    path = _path(analysis_id)
    if not path.is_file():
        return None
    return AnalyzeResponse.model_validate_json(path.read_text(encoding="utf-8"))


def update_notice_review(analysis_id: str, reviewer_id: str) -> bool:
    """Stamp a reviewer and reviewed_at timestamp onto a persisted analysis.

    Reads the JSON file, adds/updates the review fields, and overwrites it. Returns
    False when the analysis file does not exist.

    In this local MVP a generated notice is represented by its analysis record, so the
    review lands on `{analysis_id}.json`. Extra fields are ignored when the file is
    later read back into `AnalyzeResponse`.
    """
    path = _path(analysis_id)
    if not path.is_file():
        return False
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["reviewer_id"] = reviewer_id
    payload["reviewed_at"] = datetime.now(timezone.utc).isoformat()
    _write_text_atomic(path, json.dumps(payload, indent=2))
    logger.info("review recorded on analysis %s (reviewer %s)", analysis_id, reviewer_id)
    return True
