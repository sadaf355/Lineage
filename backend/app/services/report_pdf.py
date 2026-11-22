"""
Renders an IncidentReportPayload to an actual PDF file, using reportlab.
This is what backs the "Download PDF" button in the frontend — not a
placeholder that just re-serves the JSON with a different content type.
"""
import io
from pathlib import Path
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)

from app.schemas.report import IncidentReportPayload

NAVY = colors.HexColor("#1F3864")
GREY = colors.HexColor("#595959")


def render_report_pdf(payload: IncidentReportPayload, incident_title: str, incident_id: str, manifest: list[dict] | None = None, language: str = "en") -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=LETTER,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    font_name = "Helvetica"
    if language == "hi":
        for fp in ("/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf", "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf"):
            if Path(fp).exists():
                try:
                    pdfmetrics.registerFont(TTFont("LineageDevanagari", fp)); font_name = "LineageDevanagari"; break
                except Exception:
                    pass
    title_style = ParagraphStyle("LTitle", parent=styles["Title"], textColor=NAVY, fontSize=22, fontName=font_name)
    h2_style = ParagraphStyle("LH2", parent=styles["Heading2"], textColor=NAVY, spaceBefore=14, fontName=font_name)
    body_style = ParagraphStyle("LBody", parent=styles["BodyText"], leading=15, fontName=font_name)
    meta_style = ParagraphStyle("LMeta", parent=styles["Normal"], textColor=GREY, fontSize=9, fontName=font_name)

    labels = {
        "en": {"title":"LINEAGE — Incident Report","summary":"1. Executive Summary","confidence":"2. Confidence Breakdown","evidence":"3. Evidence Summary","integrity":"4. Evidence Integrity Manifest","actions":"5. Recommended Next Actions"},
        "hi": {"title":"LINEAGE — घटना रिपोर्ट","summary":"1. संक्षिप्त सारांश","confidence":"2. विश्वास/साक्ष्य विश्लेषण","evidence":"3. साक्ष्य सारांश","integrity":"4. साक्ष्य अखंडता मैनिफेस्ट","actions":"5. अनुशंसित अगले कदम"},
    }.get(language, None) or {"title":"LINEAGE — Incident Report","summary":"1. Executive Summary","confidence":"2. Confidence Breakdown","evidence":"3. Evidence Summary","integrity":"4. Evidence Integrity Manifest","actions":"5. Recommended Next Actions"}
    story = []
    story.append(Paragraph(labels["title"], title_style))
    story.append(Paragraph(f"Case: {incident_title} &nbsp;&middot;&nbsp; ID: {incident_id}", meta_style))
    story.append(Spacer(1, 10))
    story.append(HRFlowable(width="100%", color=NAVY, thickness=1))
    story.append(Spacer(1, 14))

    story.append(Paragraph(labels["summary"], h2_style))
    story.append(Paragraph(payload.summary, body_style))

    story.append(Paragraph(labels["confidence"], h2_style))
    rows = [["Metric", "Value"]]
    for item in payload.confidence_breakdown:
        value_str = item.note if item.note else f"{item.value:.0f}%"
        rows.append([item.label, value_str])
    table = Table(rows, colWidths=[3.5 * inch, 2 * inch])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(table)

    story.append(Paragraph(labels["evidence"], h2_style))
    story.append(Paragraph(
        f"Sources: {payload.source_count} &nbsp;&middot;&nbsp; Evidence items: {payload.evidence_count}",
        body_style,
    ))

    if manifest:
        story.append(Paragraph(labels["integrity"], h2_style))
        rows = [["Item", "SHA-256", "Captured"]]
        for item in manifest:
            rows.append([item.get("label", "Evidence"), item.get("sha256", "—"), item.get("captured_at", "—")])
        table = Table(rows, colWidths=[2.2 * inch, 3.1 * inch, 1.3 * inch], repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), NAVY), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")), ("FONTSIZE", (0, 0), (-1, -1), 7),
            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        story.append(table)
        story.append(Paragraph("The following Section 63 BSA statement is a template for review by qualified counsel; it is not legal advice and does not certify admissibility.", meta_style))
        story.append(Paragraph("Section 63 BSA Certificate Template: I certify that the electronic record identified above was produced/stored in the ordinary course of the relevant system's operation, and that the hash values are recorded from the preserved files at the time of capture. Complete the statutory particulars and signer details with legal guidance before relying on this certificate.", body_style))

    story.append(Paragraph(labels["actions"], h2_style))
    for i, action in enumerate(payload.recommended_actions, start=1):
        story.append(Paragraph(f"<b>{i}. {action.title}</b> — {action.detail}", body_style))
        story.append(Spacer(1, 4))

    story.append(Spacer(1, 20))
    story.append(HRFlowable(width="100%", color=colors.HexColor("#CCCCCC"), thickness=0.5))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "This report is an investigative lead based on available evidence, not proof of a "
        "person's identity, intent, or responsibility.",
        meta_style,
    ))

    doc.build(story)
    return buf.getvalue()
