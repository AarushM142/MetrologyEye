"""Form-I inspection notice as PDF, via ReportLab (Phase 8).

The generator takes the **full analysis JSON** (as persisted by local storage) plus the
inspector details, and renders a legal notice that is honest about what it is:

  * A large banner announces the document is a *preliminary, AI-assisted draft* that
    requires officer verification — the notice must never read as a finished legal act.
  * A findings table lists every VIOLATION / WARNING / MANUAL_REQUIRED with its rule id,
    message, and statutory citation, with each unverified citation marked `[unverified]`
    inline so a reader cannot miss it.
  * A signature block with Reviewed by / Officer ID / Date lines.

The function returns raw PDF bytes for direct serving to the browser.
"""

from __future__ import annotations

import io
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.schemas import AnalyzeResponse, NoticeRequest, Severity

# Only findings that demand attention appear in the table. Compliant markers are
# deliberately excluded — the notice is a document about problems to verify.
_FINDING_SEVERITIES = {Severity.VIOLATION, Severity.WARNING, Severity.MANUAL_REQUIRED}

_SEVERITY_COLOUR = {
    Severity.VIOLATION: colors.HexColor("#B91C1C"),
    Severity.WARNING: colors.HexColor("#B45309"),
    Severity.MANUAL_REQUIRED: colors.HexColor("#6B7280"),
}

_SEVERITY_HEX = {
    Severity.VIOLATION: "#B91C1C",
    Severity.WARNING: "#B45309",
    Severity.MANUAL_REQUIRED: "#6B7280",
}

_BANNER_TEXT = "PRELIMINARY ASSESSMENT — AI-ASSISTED DRAFT — REQUIRES OFFICER VERIFICATION"


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "banner": ParagraphStyle(
            "Banner",
            parent=base["Title"],
            fontSize=15,
            leading=19,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#7F1D1D"),
        ),
        "subtitle": ParagraphStyle(
            "Subtitle",
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


def _citation(citation: str, verified: bool) -> str:
    """Return the citation, flagged inline when it has not been checked against the statute."""
    return f"{citation} [unverified]" if not verified else citation


def _kv_table(pairs: list[tuple[str, str]], styles: dict[str, ParagraphStyle]) -> Table:
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


def _findings_table(
    findings: list,
    styles: dict[str, ParagraphStyle],
) -> Table:
    rows: list[list] = [
        [
            Paragraph("<b>Rule ID</b>", styles["cell"]),
            Paragraph("<b>Message</b>", styles["cell"]),
            Paragraph("<b>Statutory reference</b>", styles["cell"]),
        ]
    ]
    for finding in findings:
        rows.append(
            [
                Paragraph(
                    f"<font color='{_SEVERITY_HEX.get(finding.severity, '#111827')}'><b>{finding.rule_id}</b></font>",
                    styles["cell"],
                ),
                Paragraph(finding.message, styles["cell"]),
                Paragraph(_citation(finding.citation, finding.verified_citation), styles["cell"]),
            ]
        )

    table = Table(rows, colWidths=[42 * mm, 66 * mm, 57 * mm], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D1D5DB")),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#FEE2E2")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _signature_block(styles: dict[str, ParagraphStyle]) -> Table:
    """Reviewed by / Officer ID / Date lines with space to sign."""
    lines = ["Reviewed by:", "Officer ID:", "Date:"]
    rows = [[Paragraph(f"<b>{line}</b>", styles["small"]), Paragraph("", styles["small"])] for line in lines]
    table = Table(rows, colWidths=[60 * mm, 105 * mm])
    table.setStyle(
        TableStyle(
            [
                ("LINEBELOW", (1, 0), (1, -1), 0.6, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 14),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return table


def build_notice(
    analysis: dict,
    request: NoticeRequest,
    today: date | None = None,
) -> bytes:
    """Render the Form-I notice from a persisted analysis JSON dict. Returns PDF bytes.

    `analysis` is the full analysis payload as stored by local storage. `today` is
    injectable so the output is reproducible in tests; production passes None.
    """
    model = AnalyzeResponse.model_validate(analysis)
    today = today or date.today()
    styles = _styles()

    findings = [f for f in model.findings if f.severity in _FINDING_SEVERITIES]

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Form I Inspection Notice — {model.analysis_id[:8]}",
        author="MetrologyEye",
    )

    story: list = [
        # --- banner ----------------------------------------------------------
        Paragraph(_BANNER_TEXT, styles["banner"]),
        Spacer(1, 2 * mm),
        Paragraph(
            "Notice of contravention of the Legal Metrology (Packaged Commodities) "
            "Rules, 2011 — issued under the Legal Metrology Act, 2009",
            styles["subtitle"],
        ),
        Spacer(1, 5 * mm),
        HRFlowable(width="100%", thickness=1.2, color=colors.HexColor("#7F1D1D")),
        Spacer(1, 4 * mm),
    ]

    # --- provenance ----------------------------------------------------------
    story += [
        Paragraph("1. Inspection particulars", styles["h2"]),
        _kv_table(
            [
                ("Notice reference", model.analysis_id),
                ("Date of inspection", today.strftime("%d %B %Y")),
                ("Reviewed by (Inspector)", request.inspector_name or ""),
                ("Designation", request.inspector_designation or ""),
                ("Premises / source", request.premises or ("E-commerce listing" if model.source == "url" else "")),
                ("Method", "Automated label analysis (MetrologyEye), pending officer verification"),
            ],
            styles,
        ),
        Paragraph("2. Package particulars", styles["h2"]),
        _kv_table(
            [
                (d.field.value if hasattr(d.field, "value") else str(d.field), d.value)
                for d in model.declarations
            ]
            or [("Declarations found", "None could be read from the label")],
            styles,
        ),
    ]

    # --- findings ------------------------------------------------------------
    story.append(Paragraph("3. Findings for verification", styles["h2"]))
    if findings:
        story.append(_findings_table(findings, styles))
        if any(not f.verified_citation for f in findings):
            story += [
                Spacer(1, 2 * mm),
                Paragraph(
                    "References marked <b>[unverified]</b> have not been checked against the "
                    "official statute text. Confirm each before acting on it.",
                    styles["small"],
                ),
            ]
    else:
        story.append(
            Paragraph(
                "No violations, warnings or manual-verification items were recorded.",
                styles["body"],
            )
        )

    # --- disclosures ---------------------------------------------------------
    story += [
        Spacer(1, 8 * mm),
        HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#9CA3AF")),
        Spacer(1, 3 * mm),
        Paragraph("Basis and limitations", styles["h2"]),
        Paragraph(
            "• This document is an <b>AI-assisted preliminary draft</b> and does not, by "
            "itself, constitute a legal notice. Every declaration and citation above must "
            "be verified by a Legal Metrology Officer against the physical package and the "
            "official statute before any action is taken.",
            styles["small"],
        ),
    ]
    if model.scale is not None:
        story.append(
            Paragraph(
                f"• Letter-height measurements use a scale of {model.scale.px_per_mm:.2f} px/mm "
                f"(source: {model.scale.source.value}, confidence {model.scale.confidence:.0%}). "
                f"{model.scale.note}",
                styles["small"],
            )
        )
    if model.manual_inspection_required:
        story.append(
            Paragraph(
                "• <b>Manual inspection is required.</b> The analysis was degraded to a degree "
                "that its findings cannot stand on their own.",
                styles["small"],
            )
        )

    # --- signature block -----------------------------------------------------
    story += [Spacer(1, 16 * mm), _signature_block(styles)]

    doc.build(story)
    return buffer.getvalue()
