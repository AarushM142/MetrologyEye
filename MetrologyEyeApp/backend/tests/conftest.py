"""Shared test fixtures: keep the suite fully offline, deterministic and fast.

The VLM call in `extract.py` is stubbed at the network boundary, so tests never touch the
DeepInfra API — no key, no network, no latency, no nondeterminism. Extraction still runs
the real parse/fuse/rules pipeline against a fixed, deliberately non-compliant fixture
response, so the seeded violations are stable across every run and the whole suite is
self-contained.
"""

from __future__ import annotations

import json

import pytest

from app.config import get_settings
from app.services import extract

# Pinned so `/health` and any test asserting the model are stable regardless of `.env`.
TEST_VLM_MODEL = "meta-llama/Llama-3.2-90B-Vision-Instruct"

# Mirrors app/fixtures.py: a deliberately non-compliant label that trips three rules.
# No `country_of_origin`          -> MISSING_DECLARATION
# "500 gms" (non-standard symbol) -> UNIT_NONSTANDARD
# "Rs. 145.00" with no tax wording-> MRP_TAX_WORDING_MISSING
_FIXTURE_VALUES: dict[str, str] = {
    "commodity_name": "Refined Sunflower Oil",
    "manufacturer_name": "Suraj Foods Private Limited",
    "manufacturer_address": "Plot 14, MIDC Area, Nashik, Maharashtra 422007",
    "net_quantity": "500 gms",
    "mrp": "Rs. 145.00",
    "manufacture_date": "03/2026",
    "best_before": "Best before 9 months from packaging",
    "consumer_care": "care@surajfoods.example / 1800-000-000",
    "fssai_number": "10012043000123",
    "full_text": (
        "SURAJ Refined Sunflower Oil Net Quantity: 500 gms MRP Rs. 145.00 "
        "Mfd: 03/2026 Best before 9 months from packaging Mfd by Suraj Foods "
        "Private Limited Plot 14, MIDC Area, Nashik, Maharashtra 422007"
    ),
    "ocr_corrections": "",
}


class _FakeResponse:
    """Minimal stand-in for the `httpx.Response` the extractor reads."""

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"choices": [{"message": {"content": json.dumps(_FIXTURE_VALUES)}}]}


def _fake_post(*args, **kwargs) -> _FakeResponse:
    return _FakeResponse()


@pytest.fixture(autouse=True)
def offline_vlm(monkeypatch):
    """Force the DeepInfra path and stub the network call for every test.

    `get_settings` is cached and shared with `app.main`, so mutating the instance here is
    visible to `/health` too. `monkeypatch` restores everything after each test.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "deepinfra_api_key", "test-key")
    monkeypatch.setattr(settings, "deepinfra_model", TEST_VLM_MODEL)
    monkeypatch.setattr(extract.httpx, "post", _fake_post)
    yield
