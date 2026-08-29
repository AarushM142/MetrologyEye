"""Demo fixtures.

These exist for two real reasons, not as scaffolding:

1. **Offline operation.** With no `DEEPINFRA_API_KEY`, `extract.py` serves `fixture_extraction()`
   and the run is flagged `EXTRACT_MOCKED`. Everything downstream — rules, findings, the
   Form-I notice — is the real code path, so the deliverable stays demonstrable without a key.
2. **Demo insurance.** A live demo that depends on a network call to a third party is a
   demo that can fail in front of judges.

The fixture is a *deliberately non-compliant* label: "500 gms" (non-standard unit symbol),
an MRP with no tax-inclusive wording, and no country of origin. Each of those trips a
distinct rule, so the fixture exercises the engine rather than flattering it.
"""

from __future__ import annotations

from app.schemas import DeclarationField
from app.services.extract import ExtractionResult

FIXTURE_LABEL = "Suraj Refined Sunflower Oil 500 gms pouch"

_VALUES: dict[DeclarationField, str] = {
    DeclarationField.COMMODITY_NAME: "Refined Sunflower Oil",
    DeclarationField.MANUFACTURER_NAME: "Suraj Foods Private Limited",
    DeclarationField.MANUFACTURER_ADDRESS: "Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007",
    DeclarationField.NET_QUANTITY: "500 gms",  # non-standard symbol -> UNIT_NONSTANDARD
    DeclarationField.MRP: "Rs. 145.00",  # no tax wording -> MRP_TAX_WORDING_MISSING
    DeclarationField.MANUFACTURE_DATE: "03/2026",
    DeclarationField.BEST_BEFORE: "Best before 9 months from packaging",
    DeclarationField.CONSUMER_CARE: "care@surajfoods.example / 1800-000-000",
    DeclarationField.FSSAI_NUMBER: "10012043000123",
    # COUNTRY_OF_ORIGIN deliberately absent -> MISSING_DECLARATION
}

_FULL_TEXT = " ".join(
    [
        "SURAJ Refined Sunflower Oil",
        "Net Quantity: 500 gms",
        "MRP Rs. 145.00",
        "Mfd: 03/2026",
        "Best before 9 months from packaging",
        "Mfd by Suraj Foods Private Limited,",
        "Plot 14, MIDC Industrial Area, Nashik, Maharashtra 422007",
        "Consumer care: care@surajfoods.example / 1800-000-000",
        "FSSAI Lic. No. 10012043000123",
        "Store in a cool dry place away from sunlight",
    ]
)


def fixture_extraction() -> ExtractionResult:
    """A realistic, intentionally non-compliant extraction.

    Returns fresh copies — callers mutate `degraded`, and shared state across requests
    would leak one run's flags into the next.
    """
    return ExtractionResult(values=dict(_VALUES), full_text=_FULL_TEXT, confidence=0.85)
