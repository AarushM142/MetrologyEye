"""Declaration fields, severities, exemption results, and finding records.

These types are the statutory vocabulary of the system.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# (x, y, width, height) in pixels of the *preprocessed* image: [x, y, w, h].
BBox = tuple[int, int, int, int]


class Severity(str, Enum):
    """Maps to the evidence-viewer colours and decision status."""

    VIOLATION = "VIOLATION"  # red box
    WARNING = "WARNING"  # yellow overlay
    MANUAL_REQUIRED = "MANUAL_REQUIRED"  # grey/hatched box (e.g. font-check with no reliable scale)
    COMPLIANT = "COMPLIANT"  # green box
    POTENTIAL_NON_COMPLIANCE = "POTENTIAL_NON_COMPLIANCE"


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


class ExemptionResult(BaseModel):
    """Outcome of evaluating one statutory exemption (e.g. institutional pack, tiny pack)."""

    id: str
    matched: bool
    citation: str
    description: str | None = None
    suppressed_rules: list[str] = Field(default_factory=list)


class Finding(BaseModel):
    """One rule outcome against one declaration."""

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
    field: DeclarationField | str | None = None
    bbox: BBox | None = None
    observed: str | None = Field(default=None, description="What was found on the label")
    expected: str | None = Field(default=None, description="What the rule requires")
    confidence: float | None = Field(default=None, description="Rule-evaluation confidence")
    evidence: dict[str, Any] | None = Field(default=None, description="Detailed evidence dictionary")


# Alias for backwards compatibility / Plan terminology
Violation = Finding
