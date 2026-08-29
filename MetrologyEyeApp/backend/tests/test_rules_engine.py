"""Rule engine tests.

This file is where the "100% deterministic validation" NFR is demonstrated rather than
asserted in a slide. Three properties are tested explicitly:

  * every rule fires on a crafted input and stays silent on a clean one;
  * identical input yields byte-identical output, repeatedly;
  * output does not depend on input ordering or on dict iteration order.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.schemas import Declaration, DeclarationField, ScaleInfo, ScaleSource, Severity
from app.services.rules.engine import evaluate, evaluate_exemptions, load_catalogue

TODAY = date(2026, 8, 27)  # fixed, so date-dependent rules are reproducible

TAX_WORDING = "MRP Rs. 145.00 (inclusive of all taxes)"


def declaration(
    field: DeclarationField,
    value: str,
    *,
    bbox: tuple[int, int, int, int] | None = (10, 10, 100, 20),
    geometry: str = "ocr",
    height_mm: float | None = None,
) -> Declaration:
    return Declaration(
        field=field,
        value=value,
        bbox=bbox,
        confidence=0.9,
        geometry_source=geometry,  # type: ignore[arg-type]
        text_height_mm=height_mm,
    )


def compliant_set() -> list[Declaration]:
    """Every mandatory declaration present and well-formed. Must yield zero violations."""
    return [
        declaration(DeclarationField.COMMODITY_NAME, "Refined Sunflower Oil"),
        declaration(DeclarationField.MANUFACTURER_NAME, "Suraj Foods Private Limited"),
        declaration(DeclarationField.MANUFACTURER_ADDRESS, "Plot 14, Nashik, Maharashtra 422007"),
        declaration(DeclarationField.NET_QUANTITY, "500 g"),
        declaration(DeclarationField.MRP, TAX_WORDING),
        declaration(DeclarationField.MANUFACTURE_DATE, "03/2026"),
        declaration(DeclarationField.CONSUMER_CARE, "care@surajfoods.example"),
        declaration(DeclarationField.COUNTRY_OF_ORIGIN, "India"),
    ]


def rule_ids(findings, severity: Severity | None = None) -> set[str]:
    return {f.rule_id for f in findings if severity is None or f.severity is severity}


# --- clean baseline ---------------------------------------------------------------


def test_compliant_set_yields_no_violations():
    findings = evaluate(compliant_set(), full_text=TAX_WORDING, today=TODAY)
    assert rule_ids(findings, Severity.VIOLATION) == set()


def test_compliant_set_emits_green_markers_for_each_declaration():
    """Compliant declarations must produce findings too — the viewer draws green boxes."""
    findings = evaluate(compliant_set(), full_text=TAX_WORDING, today=TODAY)
    compliant = [f for f in findings if f.severity is Severity.COMPLIANT]
    assert len(compliant) == len(compliant_set())


# --- missing declarations ---------------------------------------------------------


@pytest.mark.parametrize("omitted", load_catalogue().mandatory)
def test_each_mandatory_declaration_is_required(omitted: DeclarationField):
    declarations = [d for d in compliant_set() if d.field is not omitted]
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    missing = [f for f in findings if f.rule_id == "MISSING_DECLARATION"]
    assert [f.field for f in missing] == [omitted]
    assert missing[0].severity is Severity.VIOLATION


def test_advisory_declarations_are_warnings_not_violations():
    findings = evaluate(compliant_set(), full_text=TAX_WORDING, today=TODAY)
    advisory = [f for f in findings if f.rule_id == "MISSING_ADVISORY"]
    assert advisory, "best_before / fssai_number should be flagged as advisory"
    assert all(f.severity is Severity.WARNING for f in advisory)


# --- unit rules -------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected_unit",
    [("500 gms", "g"), ("500 GM", "g"), ("1 ltr", "l"), ("2 Kgs", "kg"), ("250 grams", "g")],
)
def test_nonstandard_units_are_violations(value: str, expected_unit: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, value))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    hits = [f for f in findings if f.rule_id == "UNIT_NONSTANDARD"]
    assert len(hits) == 1
    assert expected_unit in hits[0].message
    assert hits[0].severity is Severity.VIOLATION


@pytest.mark.parametrize("value", ["500 g", "1.5 kg", "250 ml", "1 l", "50 mg"])
def test_standard_units_pass(value: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, value))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    assert rule_ids(findings, Severity.VIOLATION) == set()


def test_nonstandard_unit_reported_once_not_also_as_unit_missing():
    """One defect, one finding. 'gms' is non-standard, not unit-less."""
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 gms"))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    assert "UNIT_NONSTANDARD" in rule_ids(findings)
    assert "UNIT_MISSING" not in rule_ids(findings)


def test_quantity_without_any_unit_is_a_violation():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500"))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    assert "UNIT_MISSING" in rule_ids(findings, Severity.VIOLATION)


# --- MRP rules --------------------------------------------------------------------


def test_mrp_without_tax_wording_is_a_violation():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MRP]
    declarations.append(declaration(DeclarationField.MRP, "Rs. 145.00"))
    findings = evaluate(declarations, full_text="Rs. 145.00", today=TODAY)
    assert "MRP_TAX_WORDING_MISSING" in rule_ids(findings, Severity.VIOLATION)


def test_tax_wording_elsewhere_on_label_satisfies_the_rule():
    """The phrase usually sits beside the price, not inside the extracted MRP value."""
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MRP]
    declarations.append(declaration(DeclarationField.MRP, "Rs. 145.00"))
    findings = evaluate(
        declarations,
        full_text="MRP Rs. 145.00 Maximum retail price inclusive of all taxes",
        today=TODAY,
    )
    assert "MRP_TAX_WORDING_MISSING" not in rule_ids(findings)


@pytest.mark.parametrize("value", ["145.00", "one hundred forty five", "MRP: --"])
def test_mrp_without_currency_is_a_violation(value: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MRP]
    declarations.append(declaration(DeclarationField.MRP, value))
    findings = evaluate(declarations, full_text=value, today=TODAY)
    assert "MRP_FORMAT_INVALID" in rule_ids(findings, Severity.VIOLATION)


@pytest.mark.parametrize("value", ["Rs. 145.00", "₹145", "INR 99.50", "rs 20"])
def test_mrp_currency_forms_accepted(value: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MRP]
    declarations.append(declaration(DeclarationField.MRP, value))
    findings = evaluate(declarations, full_text=f"{value} inclusive of all taxes", today=TODAY)
    assert "MRP_FORMAT_INVALID" not in rule_ids(findings)


# --- manufacture date -------------------------------------------------------------


@pytest.mark.parametrize("value", ["03/2026", "MAR 2026", "03-2026", "March 2026", "2026/03"])
def test_valid_manufacture_dates_pass(value: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MANUFACTURE_DATE]
    declarations.append(declaration(DeclarationField.MANUFACTURE_DATE, value))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    assert "MFG_DATE_INVALID" not in rule_ids(findings), f"{value} should parse"


@pytest.mark.parametrize("value", ["not a date", "13/2026", "03/1998", "----"])
def test_unreadable_or_implausible_dates_are_violations(value: str):
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MANUFACTURE_DATE]
    declarations.append(declaration(DeclarationField.MANUFACTURE_DATE, value))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    assert "MFG_DATE_INVALID" in rule_ids(findings, Severity.VIOLATION)


def test_future_manufacture_date_gets_its_own_message():
    """A future date is a false declaration, not an illegible one — say which."""
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.MANUFACTURE_DATE]
    declarations.append(declaration(DeclarationField.MANUFACTURE_DATE, "12/2026"))
    findings = evaluate(declarations, full_text=TAX_WORDING, today=TODAY)
    hits = [f for f in findings if f.rule_id == "MFG_DATE_INVALID"]
    assert len(hits) == 1
    assert "future" in hits[0].message.lower()


# --- font height ------------------------------------------------------------------

SCALE = ScaleInfo(px_per_mm=7.5, confidence=0.8, source=ScaleSource.EAN13)


def test_small_text_is_a_warning_never_a_violation():
    """The scale behind this measurement is an estimate. A violation would overclaim."""
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=SCALE, today=TODAY)
    hits = [f for f in findings if f.rule_id == "FONT_HEIGHT_BELOW_MIN"]
    assert len(hits) == 1
    assert hits[0].severity is Severity.WARNING
    assert "advisory" in hits[0].message.lower()


def test_font_check_suppressed_without_a_scale():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=None, today=TODAY)
    assert "FONT_HEIGHT_BELOW_MIN" not in rule_ids(findings)


def test_font_check_suppressed_for_vlm_geometry():
    """VLM boxes are too coarse to measure millimetres; measuring them anyway invents data."""
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(
        declaration(DeclarationField.NET_QUANTITY, "500 g", geometry="vlm", height_mm=0.4)
    )
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=SCALE, today=TODAY)
    assert "FONT_HEIGHT_BELOW_MIN" not in rule_ids(findings)


def test_adequate_font_height_passes():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=2.5))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=SCALE, today=TODAY)
    assert "FONT_HEIGHT_BELOW_MIN" not in rule_ids(findings)


# --- determinism ------------------------------------------------------------------


def defective_set() -> list[Declaration]:
    """Trips several rules at once, so determinism is tested on a non-trivial output."""
    declarations = [
        d
        for d in compliant_set()
        if d.field
        not in {
            DeclarationField.NET_QUANTITY,
            DeclarationField.MRP,
            DeclarationField.COUNTRY_OF_ORIGIN,
        }
    ]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 gms", height_mm=0.5))
    declarations.append(declaration(DeclarationField.MRP, "145.00"))
    return declarations


def serialise(findings) -> str:
    return "\n".join(f.model_dump_json() for f in findings)


def test_identical_input_yields_byte_identical_output():
    """The determinism NFR, stated at the boundary where it actually holds."""
    runs = [
        serialise(evaluate(defective_set(), full_text="145.00", scale=SCALE, today=TODAY))
        for _ in range(8)
    ]
    assert len(set(runs)) == 1


def test_output_is_independent_of_input_ordering():
    forward = defective_set()
    findings_forward = evaluate(forward, full_text="145.00", scale=SCALE, today=TODAY)
    findings_reverse = evaluate(list(reversed(forward)), full_text="145.00", scale=SCALE, today=TODAY)
    assert serialise(findings_forward) == serialise(findings_reverse)


def test_findings_are_ordered_violations_then_warnings_then_compliant():
    findings = evaluate(defective_set(), full_text="145.00", scale=SCALE, today=TODAY)
    rank = {Severity.VIOLATION: 0, Severity.WARNING: 1, Severity.COMPLIANT: 2}
    ranks = [rank[f.severity] for f in findings]
    assert ranks == sorted(ranks)


def test_defective_set_fires_every_expected_rule():
    findings = evaluate(defective_set(), full_text="145.00", scale=SCALE, today=TODAY)
    assert {
        "UNIT_NONSTANDARD",
        "MRP_FORMAT_INVALID",
        "MRP_TAX_WORDING_MISSING",
        "MISSING_DECLARATION",
    } <= rule_ids(findings, Severity.VIOLATION)
    assert "FONT_HEIGHT_BELOW_MIN" in rule_ids(findings, Severity.WARNING)


# --- citation integrity -----------------------------------------------------------
def test_every_citation_is_marked_unverified_until_checked():
    """Guards the one defect that would discredit the deliverable: a notice that presents
    an unchecked statutory reference as confirmed. Flip a rule's `verified: true` in the
    catalogue only after reading the statute — and update this test deliberately."""
    findings = evaluate(defective_set(), full_text="145.00", scale=SCALE, today=TODAY)
    assert findings, "expected findings to check"
    assert all(not f.verified_citation for f in findings)
    assert all(f.citation for f in findings)


# --- Phase 6: exemptions ----------------------------------------------------------


def _net_qty(value: str) -> list[Declaration]:
    return [
        d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY
    ] + [declaration(DeclarationField.NET_QUANTITY, value)]


def test_evaluate_exemptions_returns_all_three_with_reasons():
    """Every exemption is reported (matched or not) so the API can say *why*."""
    results = evaluate_exemptions(compliant_set(), full_text=TAX_WORDING)
    ids = [r.id for r in results]
    assert ids == ["EXEMPT_INSTITUTIONAL", "EXEMPT_AGRI_PRODUCE", "EXEMPT_SMALL_PACK_FONT"]
    for r in results:
        assert r.citation
        assert r.description
        assert r.suppressed_rules


def test_agri_bulk_exemption_matches_over_25kg_and_suppresses_all():
    results = evaluate_exemptions(_net_qty("30 kg"), full_text="")
    matched = next(r for r in results if r.id == "EXEMPT_AGRI_PRODUCE")
    assert matched.matched
    assert "ALL" in matched.suppressed_rules

    findings = evaluate(_net_qty("30 kg"), full_text=TAX_WORDING, today=TODAY, exemptions=results)
    assert findings == [], "an ALL exemption must suppress the entire analysis"


def test_small_pack_exemption_suppresses_only_font_height():
    """<=10 g/ml skips the font check but keeps the other rules running."""
    results = evaluate_exemptions(_net_qty("8 g"), full_text=TAX_WORDING)
    matched = next(r for r in results if r.id == "EXEMPT_SMALL_PACK_FONT")
    assert matched.matched
    assert matched.suppressed_rules == ["FONT_HEIGHT_BELOW_MIN"]

    declarations = [d for d in _net_qty("8 g") if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "8 g", height_mm=0.3))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=SCALE, today=TODAY, exemptions=results)
    assert "FONT_HEIGHT_BELOW_MIN" not in rule_ids(findings)
    # other rules still fire on the non-exempt declarations
    assert rule_ids(findings, Severity.VIOLATION) == set()


def test_institutional_exemption_matches_keyword_and_suppresses_all():
    declarations = _net_qty("500 g")
    declarations.append(declaration(DeclarationField.COMMODITY_NAME, "Bulk industrial packaging"))
    results = evaluate_exemptions(declarations, full_text="for institutional use only")
    matched = next(r for r in results if r.id == "EXEMPT_INSTITUTIONAL")
    assert matched.matched
    assert "ALL" in matched.suppressed_rules


def test_unmatched_exemption_does_not_suppress():
    results = evaluate_exemptions(_net_qty("500 g"), full_text=TAX_WORDING)
    assert all(not r.matched for r in results)
    findings = evaluate(defective_set(), full_text="145.00", scale=SCALE, today=TODAY, exemptions=results)
    assert rule_ids(findings, Severity.VIOLATION), "no exemption matched — rules must run"


# --- Phase 6: scale tier + font height --------------------------------------------


def tier_scale(tier: str) -> ScaleInfo:
    return ScaleInfo(px_per_mm=7.5, confidence=0.8, source=ScaleSource.EAN13, tier=tier)  # type: ignore[arg-type]


def test_medium_tier_font_check_is_forced_to_warning():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=tier_scale("MEDIUM"), today=TODAY)
    hits = [f for f in findings if f.rule_id == "FONT_HEIGHT_BELOW_MIN"]
    assert len(hits) == 1
    assert hits[0].severity is Severity.WARNING


def test_manual_required_tier_suppresses_font_and_emits_manual_finding():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=tier_scale("MANUAL_REQUIRED"), today=TODAY)
    assert "FONT_HEIGHT_BELOW_MIN" not in rule_ids(findings)
    manual = [f for f in findings if f.severity is Severity.MANUAL_REQUIRED]
    assert len(manual) == 1
    assert "manual verification required" in manual[0].message.lower()


def test_high_tier_font_check_runs_normally():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    findings = evaluate(declarations, full_text=TAX_WORDING, scale=tier_scale("HIGH"), today=TODAY)
    hits = [f for f in findings if f.rule_id == "FONT_HEIGHT_BELOW_MIN"]
    assert len(hits) == 1
    assert hits[0].severity is Severity.WARNING
    assert not any(f.severity is Severity.MANUAL_REQUIRED for f in findings)


def test_manual_required_finding_is_byte_identical_across_runs():
    declarations = [d for d in compliant_set() if d.field is not DeclarationField.NET_QUANTITY]
    declarations.append(declaration(DeclarationField.NET_QUANTITY, "500 g", height_mm=0.4))
    runs = {
        serialise(evaluate(declarations, full_text=TAX_WORDING, scale=tier_scale("MANUAL_REQUIRED"), today=TODAY))
        for _ in range(6)
    }
    assert len(runs) == 1

