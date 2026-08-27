"""Declaration fields, severities, and violation records.

These types are the statutory vocabulary of the system. `Severity` in particular is
load-bearing: font-height findings are WARNING and never VIOLATION, because the
millimetre scale they rest on is an estimate (see schemas/analysis.py ScaleInfo).
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

# (x, y, width, height) in pixels of the *preprocessed* image. A tuple, not a model,
# so it serialises to a JSON array exactly as the frontend canvas expects: [x,y,w,h].
BBox = tuple[int, int, int, int]


class Severity(str, Enum):
    """Maps 1:1 onto the evidence-viewer colours in the demo spec."""

    VIOLATION = "VIOLATION"  # red box
    WARNING = "WARNING"  # yellow overlay
    COMPLIANT = "COMPLIANT"  # green box


class DeclarationField(str, Enum):
    """The mandatory declarations we look for on a package."""

    COMMODITY_NAME = "commodity_name"
    MANUFACTURER_NAME = "manufacturer_name"
    MANUFACTURER_ADDRESS = "manufacturer_address"
    NET_QUANTITY = "net_quantity"
    MRP = "mrp"
    MANUFACTURE_DATE = "manufacture_date"
    BEST_BEFORE = "best_before"
    CONSUMER_CARE = "consumer_care"
    COUNTRY_OF_ORIGIN = "country_of_origin"
    FSSAI_NUMBER = "fssai_number"


class Finding(BaseModel):
    """One rule outcome against one declaration.

    A Finding is emitted for compliant declarations too (Severity.COMPLIANT), because
    the evidence viewer must draw green boxes for what passed — an inspector needs to
    see what was checked, not only what failed.
    """

    rule_id: str = Field(description="Stable key from rules/catalogue.yaml, e.g. UNIT_NONSTANDARD")
    severity: Severity
    citation: str = Field(description="Statutory reference as written in the catalogue")
    verified_citation: bool = Field(
        default=False,
        description=(
            "True only once the citation has been checked against the official statute "
            "text. Surfaced in the API and stamped on the PDF so an unverified citation "
            "can never be mistaken for a confirmed one."
        ),
    )
    message: str = Field(description="Inspector-facing sentence, safe to print in a notice")
    field: DeclarationField | None = None
    bbox: BBox | None = None
    observed: str | None = Field(default=None, description="What was found on the label")
    expected: str | None = Field(default=None, description="What the rule requires")
