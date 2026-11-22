from __future__ import annotations

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib import colors


def build_request_pack(incident, media, sources, evidence, footprints) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40)
    styles = getSampleStyleSheet()
    story = [Paragraph("LINEAGE — Investigation Request Pack", styles["Title"]),
             Paragraph("Investigator support document. This pack does not establish identity, intent, or responsibility.", styles["BodyText"]), Spacer(1, 14),
             Paragraph(f"Case: {incident.title}", styles["Heading2"]),
             Paragraph(f"Investigation ID: {incident.id}", styles["BodyText"]), Spacer(1, 10)]
    rows = [["Artifact", "SHA-256", "Recorded time"]]
    for m in media:
        rows.append([m.original_filename, m.sha256 or "Not recorded", str(m.uploaded_at)])
    for e in evidence:
        rows.append([f"Evidence: {e.item_type}", e.sha256 or "Not recorded", str(e.captured_at)])
    for s in sources:
        if s.page_sha256:
            rows.append([f"Captured page: {s.platform}", s.page_sha256, str(s.observed_at)])
    t = Table(rows, colWidths=[180, 220, 100], repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#17352C")), ("TEXTCOLOR", (0,0), (-1,0), colors.white), ("GRID", (0,0), (-1,-1), .25, colors.grey), ("FONTSIZE", (0,0), (-1,-1), 7), ("VALIGN", (0,0), (-1,-1), "TOP")]))
    story += [t, Spacer(1, 14), Paragraph("Hosting footprints", styles["Heading2"])]
    for fp in footprints:
        story.append(Paragraph(f"{fp.get('domain','—')} — IPs: {', '.join(fp.get('server_ips', [])) or 'not resolved'} — {fp.get('country')} — {fp.get('label')}", styles["BodyText"]))
    story += [Spacer(1, 14), Paragraph("Requested records", styles["Heading2"]), Paragraph("Platform or cybercrime authority may use this pack to identify the relevant URLs, timestamps, hashes, hosting information and preserved artifacts. Platform account identity or creator IP generally requires the platform's authorized disclosure process or legal request.", styles["BodyText"]), Spacer(1, 10), Paragraph("Evidence status: investigator support, not proof. Review all source records before submission.", styles["BodyText"])]
    doc.build(story)
    return buf.getvalue()
