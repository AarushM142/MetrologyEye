"""In-memory analysis store with TTL.

Neither spec asks for persistence, so analyses live in process for
`ANALYSIS_TTL_SECONDS`. The interface is deliberately narrow (`put`/`get`/`put_image`/
`get_image`) so swapping in Supabase later touches only this file.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from app.config import get_settings
from app.schemas import AnalyzeResponse


@dataclass
class _Entry:
    analysis: AnalyzeResponse
    image_png: bytes
    created_at: float = field(default_factory=time.monotonic)


class AnalysisStore:
    def __init__(self) -> None:
        self._entries: dict[str, _Entry] = {}

    def _evict_expired(self) -> None:
        ttl = get_settings().analysis_ttl_seconds
        now = time.monotonic()
        for key in [k for k, v in self._entries.items() if now - v.created_at > ttl]:
            del self._entries[key]

    def put(self, analysis: AnalyzeResponse, image_png: bytes) -> None:
        self._evict_expired()
        self._entries[analysis.analysis_id] = _Entry(analysis=analysis, image_png=image_png)

    def get(self, analysis_id: str) -> AnalyzeResponse | None:
        self._evict_expired()
        entry = self._entries.get(analysis_id)
        return entry.analysis if entry else None

    def get_image(self, analysis_id: str) -> bytes | None:
        self._evict_expired()
        entry = self._entries.get(analysis_id)
        return entry.image_png if entry else None


store = AnalysisStore()
