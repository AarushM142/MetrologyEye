"""Deterministic rule engine.

This module is where the "100% deterministic validation" requirement is actually met, and
the boundary is worth stating precisely: **given a set of extracted declarations, the
findings are fully reproducible.** The VLM's extraction upstream is not deterministic. We
meet the NFR at this boundary and say so, rather than overclaiming it for the pipeline.

Determinism is enforced three ways:
  * no wall-clock reads except an injectable `today` (see `evaluate`);
  * no dict-iteration-order dependence — every loop runs over an explicit ordered list;
  * findings sorted by a total order before returning, so identical input yields
    byte-identical output.

`tests/test_rules_engine.py` asserts all three.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml

from app.config import get_settings
from app.schemas import (
    Declaration,
    DeclarationField,
    ExemptionResult,
    Finding,
    ScaleInfo,
    Severity,
)

# Permitted unit symbols, checked case-sensitively where the statute distinguishes case
# and folded where it does not. Used by the unit_missing check.
PERMITTED_UNITS = ("mg", "g", "kg", "ml", "cl", "dl", "l", "mm", "cm", "m", "N", "kN")

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# MRP must carry a currency indication and a number: "Rs. 145.00", "₹145", "INR 99/-".
_MRP_PATTERN = re.compile(r"(?:₹|rs\.?|inr)\s*([0-9]+(?:[.,][0-9]{1,2})?)", re.IGNORECASE)
_NUMBER_PATTERN = re.compile(r"[0-9]+(?:[.,][0-9]+)?")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE = re.compile(r"\s+")


def _normalise(text: str) -> str:
    return _SPACE.sub(" ", _PUNCT.sub(" ", text.casefold())).strip()


@dataclass(frozen=True)
class RuleDef:
    id: str
    check: str
    severity: Severity
    citation: str
    verified: bool
    description: str
    message: str
    expected: str | None = None
    params: dict = dc_field(default_factory=dict)


@dataclass(frozen=True)
class Catalogue:
    rules: dict[str, RuleDef]
    mandatory: tuple[DeclarationField, ...]
    advisory: tuple[DeclarationField, ...]
    field_labels: dict[DeclarationField, str]


def _load_catalogue(path: Path) -> Catalogue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    rules = {
        entry["id"]: RuleDef(
            id=entry["id"],
            check=entry["check"],
            severity=Severity(entry["severity"]),
            citation=entry["citation"],
            verified=bool(entry.get("verified", False)),
            description=entry.get("description", "").strip(),
            message=entry["message"].strip(),
            expected=entry.get("expected"),
            params=entry.get("params") or {},
        )
        for entry in raw["rules"]
    }

    return Catalogue(
        rules=rules,
        mandatory=tuple(DeclarationField(f) for f in raw.get("mandatory_declarations", [])),
        advisory=tuple(DeclarationField(f) for f in raw.get("advisory_declarations", [])),
        field_labels={DeclarationField(k): v for k, v in (raw.get("field_labels") or {}).items()},
    )


@lru_cache(maxsize=4)
def load_catalogue(path: Path | None = None) -> Catalogue:
    return _load_catalogue(path or get_settings().rules_catalogue_path)


# --- exemptions ------------------------------------------------------------------
# Exemptions run *before* the rule catalogue (Phase 6). An exemption that suppresses
# `ALL` short-circuits the entire evaluation; a partial exemption (e.g. `FONT_HEIGHT_*`)
# suppresses only the named rules. The reason for every exemption is returned to the
# caller via `evaluate_exemptions` so the API can tell the operator *why* rules were
# skipped.

# Sentinels matched against an exemption's `suppresses` list.
SUPPRESS_ALL = "ALL"


@dataclass(frozen=True)
class ExemptionDef:
    id: str
    citation: str
    description: str
    match: str
    suppresses: tuple[str, ...]


@dataclass(frozen=True)
class ExemptionCatalogue:
    exemptions: dict[str, ExemptionDef]
    order: tuple[str, ...]


def _load_exemptions(path: Path) -> ExemptionCatalogue:
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    entries = raw.get("exemptions") or []
    exemptions = {
        entry["id"]: ExemptionDef(
            id=entry["id"],
            citation=entry.get("citation", "").strip(),
            description=entry.get("description", "").strip(),
            match=entry["match"],
            suppresses=tuple(entry.get("suppresses") or []),
        )
        for entry in entries
    }
    return ExemptionCatalogue(exemptions=exemptions, order=tuple(exemptions.keys()))


@lru_cache(maxsize=4)
def load_exemptions(path: Path | None = None) -> ExemptionCatalogue:
    return _load_exemptions(path or get_settings().exemptions_path)


def _normalise_tokens(*texts: str) -> set[str]:
    """Normalised token set across several strings, for keyword matching."""
    return set(_SPACE.split(_normalise(" ".join(texts))))


def _quantity_in_grams(value: str) -> float | None:
    """Parse a quantity declaration into grams (or ml-equivalent). None if unreadable.

    Mass and volume are treated on the same gram/ml scale for the <=10 g/ml and
    >25 kg thresholds, which is the intent of the exemptions. Returns None when the
    value carries no recognisable unit so a plain number cannot drive an exemption.
    """
    text = _normalise(value)
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)\s*(mg|g|kg|ml|cl|dl|l)\b", text)
    if not match:
        return None
    number = float(match.group(1).replace(",", "."))
    multiplier = {
        "mg": 0.001, "g": 1.0, "kg": 1000.0,
        "ml": 1.0, "cl": 10.0, "dl": 100.0, "l": 1000.0,
    }
    return number * multiplier[match.group(2)]


def _match_institutional_pack(
    declarations: list[Declaration], full_text: str
) -> bool:
    """EXEMPT_INSTITUTIONAL: sold to industrial/institutional consumers, not retail.

    Not directly legible from a label alone — a package intended for institutional
    buyers usually carries it in the commodity name or a distribution note. Keyword
    heuristics only; treat as a stub that a human can refine.
    """
    haystack = _normalise_tokens(
        full_text, *[d.value for d in declarations], *[d.field.value for d in declarations]
    )
    institutional = {"institutional", "industrial", "institution", "hospitals", "canteen"}
    commercial = {"bulk", "wholesale", "not for retail", "for institutional use"}
    return bool(haystack & institutional) or bool(haystack & commercial)


def _match_agri_bulk_gt_25kg(
    declarations: list[Declaration], full_text: str
) -> bool:
    """EXEMPT_AGRI_PRODUCE: agricultural produce sold in bulk > 25 kg."""
    for declaration in declarations:
        if declaration.field is not DeclarationField.NET_QUANTITY:
            continue
        grams = _quantity_in_grams(declaration.value)
        if grams is not None and grams > 25000.0:
            return True
    return False


def _match_small_pack_le_10(
    declarations: list[Declaration], full_text: str
) -> bool:
    """EXEMPT_SMALL_PACK_FONT: very small package (<= 10 g/ml)."""
    for declaration in declarations:
        if declaration.field is not DeclarationField.NET_QUANTITY:
            continue
        grams = _quantity_in_grams(declaration.value)
        if grams is not None and grams <= 10.0:
            return True
    return False


_EXEMPTION_MATCHERS: dict[str, object] = {
    "institutional_pack": _match_institutional_pack,
    "agri_bulk_gt_25kg": _match_agri_bulk_gt_25kg,
    "small_pack_le_10": _match_small_pack_le_10,
}


def evaluate_exemptions(
    declarations: list[Declaration],
    full_text: str = "",
) -> list[ExemptionResult]:
    """Evaluate every exemption in catalogue order. Never raises.

    Returns an `ExemptionResult` per exemption so the API can surface the reason
    whether or not it matched. The caller passes the matched ones back into
    `evaluate(...)` for suppression, and ships all of them in the response payload.
    """
    cat = load_exemptions()
    results: list[ExemptionResult] = []
    for ex_id in cat.order:
        ex = cat.exemptions[ex_id]
        matcher = _EXEMPTION_MATCHERS.get(ex.match)
        matched = bool(matcher(declarations, full_text)) if matcher is not None else False
        results.append(
            ExemptionResult(
                id=ex.id,
                matched=matched,
                citation=ex.citation,
                description=ex.description,
                suppressed_rules=list(ex.suppresses),
            )
        )
    return results


# --- individual checks -------------------------------------------------------------
# Each returns findings for its rule only, and never mutates its inputs.


def _check_missing(
    rule: RuleDef, fields: tuple[DeclarationField, ...], present: set[DeclarationField], cat: Catalogue
) -> list[Finding]:
    return [
        Finding(
            rule_id=rule.id,
            severity=rule.severity,
            citation=rule.citation,
            verified_citation=rule.verified,
            message=rule.message.format(label=cat.field_labels.get(f, f.value)),
            field=f,
            bbox=None,  # nothing to box: the violation is the absence
            observed="Not found on label",
            expected=rule.expected,
        )
        for f in fields
        if f not in present
    ]


def _check_unit_nonstandard(rule: RuleDef, declaration: Declaration) -> list[Finding]:
    substitutions: dict[str, str] = rule.params.get("substitutions", {})
    tokens = _normalise(declaration.value).split()
    # Ordered scan over the value's own tokens, then over substitutions in catalogue
    # order — never over a set — so the reported unit is stable for a given input.
    for token in tokens:
        correct = substitutions.get(token)
        if correct is None:
            continue
        return [
            Finding(
                rule_id=rule.id,
                severity=rule.severity,
                citation=rule.citation,
                verified_citation=rule.verified,
                message=rule.message.format(observed_unit=token, correct_unit=correct),
                field=declaration.field,
                bbox=declaration.bbox,
                observed=declaration.value,
                expected=_NUMBER_PATTERN.sub(lambda m: m.group(0), declaration.value).replace(
                    token, correct
                )
                if token in declaration.value.lower()
                else f"quantity in '{correct}'",
            )
        ]
    return []


def _check_unit_missing(rule: RuleDef, declaration: Declaration) -> list[Finding]:
    tokens = set(_normalise(declaration.value).split())
    substitutions: dict[str, str] = {}
    if tokens & {u.casefold() for u in PERMITTED_UNITS}:
        return []
    # A non-standard unit is a different, more specific violation; UNIT_NONSTANDARD
    # reports it. Staying silent here avoids two findings for one defect.
    if tokens & set(substitutions) or _looks_like_nonstandard(declaration.value):
        return []
    return [
        Finding(
            rule_id=rule.id,
            severity=rule.severity,
            citation=rule.citation,
            verified_citation=rule.verified,
            message=rule.message.format(observed=declaration.value),
            field=declaration.field,
            bbox=declaration.bbox,
            observed=declaration.value,
            expected=rule.expected,
        )
    ]


def _looks_like_nonstandard(value: str) -> bool:
    """Whether the value carries a unit we recognise as non-standard.

    Consulted by UNIT_MISSING so a `gms` label is reported once (as non-standard) rather
    than twice (as non-standard *and* unit-less).
    """
    catalogue = load_catalogue()
    rule = catalogue.rules.get("UNIT_NONSTANDARD")
    if rule is None:
        return False
    return bool(set(_normalise(value).split()) & set(rule.params.get("substitutions", {})))


def _check_mrp_format(rule: RuleDef, declaration: Declaration) -> list[Finding]:
    if _MRP_PATTERN.search(declaration.value):
        return []
    return [
        Finding(
            rule_id=rule.id,
            severity=rule.severity,
            citation=rule.citation,
            verified_citation=rule.verified,
            message=rule.message.format(observed=declaration.value),
            field=declaration.field,
            bbox=declaration.bbox,
            observed=declaration.value,
            expected=rule.expected,
        )
    ]


def _check_mrp_tax_wording(rule: RuleDef, declaration: Declaration, full_text: str) -> list[Finding]:
    haystack = _normalise(f"{declaration.value} {full_text}")
    phrases: list[str] = rule.params.get("accepted_phrases", [])
    if any(_normalise(p) in haystack for p in phrases):
        return []
    return [
        Finding(
            rule_id=rule.id,
            severity=rule.severity,
            citation=rule.citation,
            verified_citation=rule.verified,
            message=rule.message,
            field=declaration.field,
            bbox=declaration.bbox,
            observed=declaration.value,
            expected=rule.expected,
        )
    ]


def _parse_month_year(value: str) -> tuple[int, int] | None:
    """Parse a manufacture date into (year, month). Returns None if unreadable.

    Only month and year are required by the rule, so a day is accepted and discarded
    rather than demanded.
    """
    text = value.casefold()

    # Numeric: 03/2026, 03-26, 2026/03
    for match in re.finditer(r"(\d{1,4})\s*[/\-.]\s*(\d{1,4})", text):
        a, b = int(match.group(1)), int(match.group(2))
        if 1 <= a <= 12 and b >= 100:
            return b, a
        if a >= 100 and 1 <= b <= 12:
            return a, b
        if 1 <= a <= 12 and 0 <= b <= 99:
            return 2000 + b, a

    # Alphabetic month: MAR 2026, March 26. Scanned in calendar order for stability.
    for name, month in sorted(_MONTHS.items(), key=lambda kv: kv[1]):
        if name not in text:
            continue
        year_match = re.search(r"(\d{4})|(?<!\d)(\d{2})(?!\d)", text)
        if not year_match:
            continue
        year = int(year_match.group(1)) if year_match.group(1) else 2000 + int(year_match.group(2))
        return year, month

    return None


def _check_mfg_date(rule: RuleDef, declaration: Declaration, today: date) -> list[Finding]:
    parsed = _parse_month_year(declaration.value)
    earliest = int(rule.params.get("earliest_year", 2015))

    if parsed is None or not (earliest <= parsed[0] <= today.year + 1):
        message = rule.message.format(observed=declaration.value)
    elif (parsed[0], parsed[1]) > (today.year, today.month):
        message = str(rule.params.get("future_message", rule.message)).format(
            observed=declaration.value
        )
    else:
        return []

    return [
        Finding(
            rule_id=rule.id,
            severity=rule.severity,
            citation=rule.citation,
            verified_citation=rule.verified,
            message=message,
            field=declaration.field,
            bbox=declaration.bbox,
            observed=declaration.value,
            expected=rule.expected,
        )
    ]


def _check_font_height(
    rule: RuleDef,
    declaration: Declaration,
    cat: Catalogue,
    scale: ScaleInfo | None,
    force_warning: bool = False,
) -> list[Finding]:
    """Letter-height check. Suppressed unless the geometry can carry it.

    Three preconditions, all load-bearing: a scale must exist, the box must come from OCR
    (VLM boxes are not precise enough to measure millimetres), and a height must have been
    measured. Failing any of them we emit nothing rather than a guess.

    `force_warning` implements the MEDIUM-tier rule: the scale is a single estimate (no
    corroborating reference object), so even a measured shortfall can only be a warning —
    it must never escalate to a violation off one unvalidated number.
    """
    if scale is None or declaration.geometry_source != "ocr" or not declaration.text_height_mm:
        return []

    minimum = float(rule.params.get("min_height_mm", 1.0))
    tolerance = float(rule.params.get("tolerance_mm", 0.15))
    if declaration.text_height_mm >= minimum - tolerance:
        return []

    severity = Severity.WARNING if force_warning else rule.severity
    return [
        Finding(
            rule_id=rule.id,
            severity=severity,  # WARNING by catalogue definition — never a violation
            citation=rule.citation,
            verified_citation=rule.verified,
            message=" ".join(
                rule.message.format(
                    label=cat.field_labels.get(declaration.field, declaration.field.value),
                    observed_mm=f"{declaration.text_height_mm:.2f}",
                    min_mm=f"{minimum:g}",
                ).split()
            ),
            field=declaration.field,
            bbox=declaration.bbox,
            observed=f"{declaration.text_height_mm:.2f} mm",
            expected=f"at least {minimum:g} mm",
        )
    ]


# --- orchestration ----------------------------------------------------------------

# Report order: problems first, then what passed. Within a severity, declaration order.
_SEVERITY_RANK = {
    Severity.VIOLATION: 0,
    Severity.WARNING: 1,
    Severity.MANUAL_REQUIRED: 2,
    Severity.COMPLIANT: 3,
}
_FIELD_RANK = {f: i for i, f in enumerate(DeclarationField)}

# Message emitted when the scale tier forbids a reliable font measurement. Carries its own
# rule id — distinct from FONT_HEIGHT_BELOW_MIN — so a suppressed font check is never
# mistaken for one that actually fired.
_MANUAL_SCALE_FINDING_RULE_ID = "SCALE_MANUAL_REQUIRED"
_MANUAL_SCALE_FINDING_MESSAGE = (
    "No reliable scale reference in frame — manual verification required."
)


def _suppressed_rules(exemptions: list[ExemptionResult] | None) -> tuple[set[str], bool]:
    """Flatten matched exemptions into (suppressed_rule_ids, all_suppressed).

    `all_suppressed` is True when any matched exemption carries the `ALL` sentinel —
    the whole analysis is suppressed. Rule ids from partial exemptions accumulate in
    `suppressed_rule_ids`. Order-independent by construction.
    """
    suppressed: set[str] = set()
    all_suppressed = False
    for exemption in exemptions or []:
        if not exemption.matched:
            continue
        if SUPPRESS_ALL in exemption.suppressed_rules:
            all_suppressed = True
        suppressed.update(r for r in exemption.suppressed_rules if r != SUPPRESS_ALL)
    return suppressed, all_suppressed


def evaluate(
    declarations: list[Declaration],
    full_text: str = "",
    scale: ScaleInfo | None = None,
    today: date | None = None,
    catalogue: Catalogue | None = None,
    exemptions: list[ExemptionResult] | None = None,
) -> list[Finding]:
    """Evaluate every rule and return findings in a stable total order.

    `today` is injectable purely so the manufacture-date check is testable and
    reproducible; production passes None and gets the real date.

    `exemptions` are the results of `evaluate_exemptions` (Phase 6 pre-filter). A
    matched exemption that suppresses `ALL` short-circuits evaluation entirely; partial
    exemptions suppress only the named rules.
    """
    cat = catalogue or load_catalogue()
    today = today or date.today()
    by_field = {d.field: d for d in declarations}
    findings: list[Finding] = []

    suppressed, all_suppressed = _suppressed_rules(exemptions)
    if all_suppressed:
        return []

    def rule(rule_id: str) -> RuleDef | None:
        return None if rule_id in suppressed else cat.rules.get(rule_id)

    if (r := rule("MISSING_DECLARATION")) is not None:
        findings += _check_missing(r, cat.mandatory, set(by_field), cat)
    if (r := rule("MISSING_ADVISORY")) is not None:
        findings += _check_missing(r, cat.advisory, set(by_field), cat)

    if (net_qty := by_field.get(DeclarationField.NET_QUANTITY)) is not None:
        if (r := rule("UNIT_NONSTANDARD")) is not None:
            findings += _check_unit_nonstandard(r, net_qty)
        if (r := rule("UNIT_MISSING")) is not None:
            findings += _check_unit_missing(r, net_qty)

    if (mrp := by_field.get(DeclarationField.MRP)) is not None:
        if (r := rule("MRP_FORMAT_INVALID")) is not None:
            findings += _check_mrp_format(r, mrp)
        if (r := rule("MRP_TAX_WORDING_MISSING")) is not None:
            findings += _check_mrp_tax_wording(r, mrp, full_text)

    if (mfg := by_field.get(DeclarationField.MANUFACTURE_DATE)) is not None:
        if (r := rule("MFG_DATE_INVALID")) is not None:
            findings += _check_mfg_date(r, mfg, today)

    if (r := rule("FONT_HEIGHT_BELOW_MIN")) is not None:
        # MANUAL_REQUIRED tier: no reliable scale reference — suppress the measurement
        # entirely and emit a single manual-verification finding. MEDIUM tier: run the
        # check but cap the outcome at WARNING regardless of the measurement.
        if scale is not None and scale.tier == "MANUAL_REQUIRED":
            findings.append(
                Finding(
                    rule_id=_MANUAL_SCALE_FINDING_RULE_ID,
                    severity=Severity.MANUAL_REQUIRED,
                    citation=r.citation,
                    verified_citation=r.verified,
                    message=_MANUAL_SCALE_FINDING_MESSAGE,
                    field=None,
                    observed=scale.tier,
                    expected="a reliable scale reference (barcode and/or reference card)",
                )
            )
        else:
            force_warning = scale is not None and scale.tier == "MEDIUM"
            # Iterate the input list, not `by_field` — list order is explicit, dict order
            # is incidental, and determinism must not rest on the incidental.
            for declaration in declarations:
                findings += _check_font_height(r, declaration, cat, scale, force_warning)

    # Green markers for declarations that drew no violation and no warning. The viewer
    # must show what was verified, not only what failed.
    if (r := rule("DECLARATION_PRESENT")) is not None:
        flagged = {f.field for f in findings if f.severity is not Severity.COMPLIANT}
        for declaration in declarations:
            if declaration.field in flagged:
                continue
            findings.append(
                Finding(
                    rule_id=r.id,
                    severity=Severity.COMPLIANT,
                    citation=r.citation,
                    verified_citation=r.verified,
                    message=r.message.format(
                        label=cat.field_labels.get(declaration.field, declaration.field.value)
                    ),
                    field=declaration.field,
                    bbox=declaration.bbox,
                    observed=declaration.value,
                )
            )

    findings.sort(
        key=lambda f: (
            _SEVERITY_RANK[f.severity],
            _FIELD_RANK.get(f.field, len(_FIELD_RANK)) if f.field else len(_FIELD_RANK),
            f.rule_id,
        )
    )
    return findings

