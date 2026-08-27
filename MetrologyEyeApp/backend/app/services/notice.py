"""Form-I inspection notice as PDF, via ReportLab.

Two things this document must do that an ordinary report need not:

1. **Show its evidence.** Each violation is accompanied by a crop of the exact region of the
   label it was found in, taken from the same preprocessed frame the boxes were computed in.
   An inspector should not have to take the software's word for anything.
2. **Disclose its own uncertainty in the document itself.** Unverified citations are marked
   inline, and the barcode-magnification assumption behind every font measurement is printed.
   A notice that hides its assumptions is worse than no notice — it is a notice that cannot
   be defended.
"""

from __future__ import annotations

import io
from datetime import date

import cv2
import numpy as np
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas import AnalyzeResponse, Finding, NoticeRequest, Severity
from app.services.rules.engine import load_catalogue, unverified_citations

_SEVERITY_COLOUR = {
    Severity.VIOLATION: colors.HexColor("#B91C1C"),
    Severity.WARNING: colors.HexColor("#B45309"),
    Severity.COMPLIANT: colors.HexColor("#15803D"),
}

# Padding around an evidence crop, so the inspector sees the declaration in context rather
# than a disembodied strip of pixels.
CROP_PAD_PX = 18
CROP_MAX_WIDTH_MM = 150.0


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "FormTitle", parent=base["Title"], fontSize=15, leading=19, alignment=TA_CENTER
        ),
        "subtitle": ParagraphStyle(
            "FormSubtitle",
            parent=base["Normal"],
            fontSize=9.5,
            leading=13,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#374151"),
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=11.5, leading=15, spaceBefore=10, spaceAfter=4
        ),
        "body": ParagraphStyle("Body", parent=base["Normal"], fontSize=9.5, leading=13),
        "small": ParagraphStyle(
            "Small",
            parent=base["Normal"],
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#4B5563"),
        ),
        "cell": ParagraphStyle("Cell", parent=base["Normal"], fontSize=8.5, leading=11),
    }


def _crop(image: np.ndarray, bbox: tuple[int, int, int, int]) -> Image | None:
    """Crop the evidence region as a flowable, or None if the box is unusable."""
    h, w = image.shape[:2]
    x, y, bw, bh = bbox
    x0, y0 = max(0, x - CROP_PAD_PX), max(0, y - CROP_PAD_PX)
    x1, y1 = min(w, x + bw + CROP_PAD_PX), min(h, y + bh + CROP_PAD_PX)
    if x1 - x0 < 4 or y1 - y0 < 4:
        return None

    patch = image[y0:y1, x0:x1].copy()
    # Draw the box on the crop, in the crop's own coordinates, so it is obvious which text
    # the finding refers to when the crop caught a neighbour too.
    cv2.rectangle(patch, (x - x0, y - y0), (x - x0 + bw, y - y0 + bh), (0, 0, 220), 2)

    ok, encoded = cv2.imencode(".png", patch)
    if not ok:
        return None

    patch_h, patch_w = patch.shape[:2]
    display_w = min(CROP_MAX_WIDTH_MM * mm, patch_w * 0.75)
    return Image(io.BytesIO(encoded.tobytes()), width=display_w, height=display_w * patch_h / patch_w)


def _finding_rows(findings: list[Finding], labels: dict, styles: dict) -> list[list]:
    rows: list[list] = [
        [
            Paragraph("<b>#</b>", styles["cell"]),
            Paragraph("<b>Declaration</b>", styles["cell"]),
            Paragraph("<b>Observation</b>", styles["cell"]),
            Paragraph("<b>Statutory reference</b>", styles["cell"]),
        ]
    ]
    for index, finding in enumerate(findings, start=1):
        label = labels.get(finding.field, finding.field.value if finding.field else "—")
        citation = finding.citation
        if not finding.verified_citation:
            # Inline, not a footnote. A reader skimming the table must not be able to miss it.
            citation += ' <font color="#B45309">[unverified]</font>'
        rows.append(
            [
                Paragraph(str(index), styles["cell"]),
                Paragraph(label, styles["cell"]),
                Paragraph(finding.message, styles["cell"]),
                Paragraph(citation, styles["cell"]),
            ]
        )
    return rows


def _kv_table(pairs: list[tuple[str, str]], styles: dict) -> Table:
    table = Table(
        [[Paragraph(f"<b>{k}</b>", styles["cell"]), Paragraph(v or "—", styles["cell"])] for k, v in pairs],
        colWidths=[58 * mm, 107 * mm],
    )
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F3F4F6")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def build_notice(
    analysis: AnalyzeResponse,
    image_png: bytes,
    request: NoticeRequest,
    today: date | None = None,
) -> bytes:
    """Render the Form-I notice. Returns PDF bytes.

    `today` is injectable so the output is reproducible in tests; production passes None.
    """
    today = today or date.today()
    styles = _styles()
    catalogue = load_catalogue()
    labels = catalogue.field_labels

    image = cv2.imdecode(np.frombuffer(image_png, np.uint8), cv2.IMREAD_COLOR)

    violations = [f for f in analysis.findings if f.severity is Severity.VIOLATION]
    warnings = [f for f in analysis.findings if f.severity is Severity.WARNING]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Form I Inspection Notice — {analysis.analysis_id[:8]}",
        author="MetrologyEye",
    )

    story: list = [
        Paragraph("FORM I", styles["title"]),
        Paragraph(
            "Notice of contravention of the Legal Metrology (Packaged Commodities) "
            "Rules, 2011<br/>issued under the Legal Metrology Act, 2009",
            styles["subtitle"],
        ),
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=0.8, color=colors.HexColor("#9CA3AF")),
        Spacer(1, 4 * mm),
    ]

    # --- provenance block --------------------------------------------------------
    declared = {d.field: d.value for d in analysis.declarations}
    story += [
        Paragraph("1. Inspection particulars", styles["h2"]),
        _kv_table(
            [
                ("Notice reference", analysis.analysis_id),
                ("Date of inspection", today.strftime("%d %B %Y")),
                ("Inspecting officer", request.inspector_name or ""),
                ("Designation", request.inspector_designation or ""),
                ("Premises / source", request.premises or ("E-commerce listing" if analysis.source == "url" else "")),
                ("Method", "Automated label analysis (MetrologyEye), reviewed by the officer named above"),
            ],
            styles,
        ),
        Paragraph("2. Package particulars", styles["h2"]),
        _kv_table(
            [(labels.get(d.field, d.field.value), d.value) for d in analysis.declarations]
            or [("Declarations found", "None could be read from the label")],
            styles,
        ),
    ]

    # --- findings ----------------------------------------------------------------
    story.append(Paragraph("3. Contraventions observed", styles["h2"]))
    if violations:
        table = Table(
            _finding_rows(violations, labels, styles),
            colWidths=[8 * mm, 40 * mm, 68 * mm, 49 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEE2E2")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TEXTCOLOR", (0, 1), (0, -1), _SEVERITY_COLOUR[Severity.VIOLATION]),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)
    else:
        story.append(
            Paragraph(
                "No contraventions were detected in the mandatory declarations examined.",
                styles["body"],
            )
        )

    if warnings:
        story += [
            Paragraph("4. Advisory observations (not contraventions)", styles["h2"]),
            Paragraph(
                "The following require physical verification before any action is taken. They "
                "rest on measurements derived from the photograph and are not asserted as "
                "contraventions.",
                styles["small"],
            ),
            Spacer(1, 2 * mm),
        ]
        table = Table(
            _finding_rows(warnings, labels, styles),
            colWidths=[8 * mm, 40 * mm, 68 * mm, 49 * mm],
            repeatRows=1,
        )
        table.setStyle(
            TableStyle(
                [
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEF3C7")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
        story.append(table)

    # --- evidence ----------------------------------------------------------------
    evidence = [f for f in violations + warnings if f.bbox is not None]
    if evidence and image is not None:
        story += [PageBreak(), Paragraph("Annexure A — Photographic evidence", styles["h2"])]
        for index, finding in enumerate(violations + warnings, start=1):
            if finding.bbox is None:
                continue
            crop = _crop(image, finding.bbox)
            if crop is None:
                continue
            label = labels.get(finding.field, finding.field.value if finding.field else "—")
            story.append(
                KeepTogether(
                    [
                        Spacer(1, 3 * mm),
                        Paragraph(f"<b>Item {index} — {label}</b>", styles["body"]),
                        Paragraph(finding.message, styles["small"]),
                        Spacer(1, 1.5 * mm),
                        crop,
                    ]
                )
            )

    # --- disclosures -------------------------------------------------------------
    story += [Spacer(1, 6 * mm), HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#9CA3AF")), Spacer(1, 3 * mm), Paragraph("Basis and limitations of this notice", styles["h2"])]

    disclosures: list[str] = [
        "This notice was prepared with automated assistance. The declarations above were "
        "read from a photograph of the package and must be confirmed against the physical "
        "package before any action is initiated.",
    ]

    if analysis.scale is not None:
        disclosures.append(
            f"Letter-height measurements use a scale of {analysis.scale.px_per_mm:.2f} px/mm "
            f"(source: {analysis.scale.source.value}, confidence {analysis.scale.confidence:.0%}). "
            f"{analysis.scale.note}"
        )
    else:
        disclosures.append(
            "No scale reference was found on the package, so no letter-height measurement "
            "was attempted. Any question of print size must be measured physically."
        )

    unverified = unverified_citations(analysis.findings)
    if unverified:
        disclosures.append(
            "<b>The following statutory references have not been verified against the "
            "official text of the statute</b> and are marked [unverified] above: "
            + "; ".join(unverified)
            + ". Confirm each reference before serving this notice."
        )

    if analysis.degraded:
        disclosures.append(
            "Image quality or capability limitations recorded during analysis: "
            + ", ".join(flag.value.replace("_", " ") for flag in analysis.degraded)
            + "."
        )
    if analysis.manual_inspection_required:
        disclosures.append(
            "<b>Manual inspection is required.</b> The analysis was degraded to a degree "
            "that its findings cannot stand on their own."
        )

    for text in disclosures:
        story += [Paragraph(f"• {text}", styles["small"]), Spacer(1, 1.5 * mm)]

    story += [
        Spacer(1, 12 * mm),
        Table(
            [[Paragraph("Signature of Inspecting Officer", styles["small"]), Paragraph("Date", styles["small"])]],
            colWidths=[105 * mm, 60 * mm],
            style=TableStyle([("LINEABOVE", (0, 0), (-1, 0), 0.6, colors.black), ("TOPPADDING", (0, 0), (-1, 0), 3)]),
        ),
    ]

    doc.build(story)
    return buffer.getvalue()
