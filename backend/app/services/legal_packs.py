"""
Draft legal/action packs. These are working drafts for a person (and ideally counsel) to review and send.
They are NOT legal advice and every PDF carries the current legal-review status. Wording that depends on a statute or rule
is kept general on purpose and flagged "confirm with counsel" where a deadline or required element is mentioned.

Regimes:
  preservation   ask a platform to keep logs/content (incl. uploader IP, login history) pending formal process
  it_rules       removal notice/complaint under India's IT Rules. Planning deadline depends on the track: order 3 h, high-risk complaint 2 h,
                 other individual complaint 36 h (see IT_TRACKS)
  tida           US TAKE IT DOWN Act removal request, intimate imagery only (planning deadline: 48 hours from a valid request)
  ncrp           complaint summary to copy into cybercrime.gov.in (the 1930 line is for financial fraud, not this)
"""
from __future__ import annotations

from datetime import datetime, timedelta
from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

TEMPLATE_VERSION = "2026.10-1"
REGIMES = ("preservation", "it_rules", "tida", "ncrp")
# India, IT Rules (as amended in 2026): the clock depends on WHAT started the request. Figures follow the law-firm summaries the
# project relied on; counsel must confirm them against the notified text. A victim's own complaint about intimate or morphed
# imagery is normally the high-risk track, not the 3-hour order track.
IT_TRACKS = {
    "order": (3, "Court order or government notice", "3 hours from receipt of the order or notice"),
    "high_risk_complaint": (2, "Individual complaint about high-risk content (nudity, intimate imagery, impersonation, morphed images)",
                            "2 hours from the complaint"),
    "individual_complaint": (36, "Other complaint by an individual", "36 hours from the complaint"),
}
DEFAULT_IT_TRACK = "high_risk_complaint"
_DEADLINE_HOURS = {"tida": 48}
_TITLES = {
    "preservation": "Preservation request (keep records pending legal process)",
    "it_rules": "Removal notice: synthetic or non-consensual intimate content (India, IT Rules)",
    "tida": "Removal request: TAKE IT DOWN Act (United States)",
    "ncrp": "Complaint summary for the National Cyber Crime Reporting Portal (cybercrime.gov.in)",
}


def deadline(regime: str, received_at: datetime | None, track: str | None = None) -> dict[str, Any] | None:
    """Planning deadline only. The binding timeline is whatever the rule or order says: confirm with counsel."""
    basis = None
    if regime == "it_rules":
        track = track or DEFAULT_IT_TRACK
        if track not in IT_TRACKS:
            raise ValueError(f"Unknown IT Rules track: {track}")
        hours, basis, _ = IT_TRACKS[track]
    else:
        hours = _DEADLINE_HOURS.get(regime)
        track = None
    if not hours or not received_at:
        return None
    due = received_at + timedelta(hours=hours)
    return {"hours": hours, "track": track, "basis": basis, "from": received_at.isoformat(sep=" ", timespec="minutes"),
            "due": due.isoformat(sep=" ", timespec="minutes"),
            "note": "Planning aid based on published summaries of the rule. Confirm the binding timeline and what starts the clock with counsel."}


def _p(text: str, style) -> Paragraph:
    return Paragraph(escape(text).replace("\n", "<br/>"), style)


def build_pack(regime: str, *, incident, media: list, sources: list, evidence: list, footprints: list[dict],
               requester: dict[str, str] | None = None, platform: str | None = None, order_received_at: datetime | None = None,
               legal_review_status: str = "pending", extra_notes: str = "", track: str | None = None) -> bytes:
    if regime not in REGIMES:
        raise ValueError(f"Unknown regime: {regime}")
    requester = requester or {}
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, rightMargin=40, leftMargin=40, topMargin=40, bottomMargin=40, pageCompression=0,
                            title=_TITLES[regime], author="LINEAGE")
    st = getSampleStyleSheet()
    body = st["BodyText"]
    story: list[Any] = []
    banner = (f"DRAFT. Legal review status: {legal_review_status.upper()}. Template {TEMPLATE_VERSION}. "
              "Not legal advice: have a lawyer review before sending." if legal_review_status != "approved" else
              f"Template {TEMPLATE_VERSION} reviewed by counsel (see your records). Check it still matches current rules before sending.")
    story += [_p(banner, st["Italic"]), Spacer(1, 8), _p(_TITLES[regime], st["Title"])]
    story += [_p(f"Case: {incident.title}   |   Reference: {incident.id}", body),
              _p(f"Prepared (UTC): {datetime.utcnow().isoformat(sep=' ', timespec='minutes')}", body)]
    if platform:
        story.append(_p(f"To: {platform}", body))
    story.append(Spacer(1, 8))

    dl = deadline(regime, order_received_at, track)
    if dl:
        label = f" ({dl['basis']})" if dl.get("basis") else ""
        story.append(_p(f"Planning deadline{label}: {dl['hours']} hours from {dl['from']} UTC, i.e. by {dl['due']} UTC. {dl['note']}", st["Italic"]))
        story.append(Spacer(1, 6))

    if regime == "preservation":
        story += [_p("1. Request", st["Heading2"]), _p(
            "I ask that you preserve, and not delete or overwrite, all records relating to the content and accounts identified below, "
            "for at least 90 days and for longer if a legal request is pending. This covers: the content and any copies or re-uploads; "
            "account identifiers; upload and creation timestamps; IP addresses and connection logs for the upload and for logins to the "
            "account; device and application identifiers; and any prior reports or removal actions.", body),
            _p("A preservation request does not itself ask you to disclose anything. A separate request through the legal process that "
               "applies (court or police order) will follow. Please confirm in writing that the records are being preserved.", body)]
    elif regime == "it_rules":
        story += [_p("1. Notice", st["Heading2"]), _p(
            "This notice concerns content that is intimate or sexually explicit, or that depicts a person in a synthetically generated or "
            "altered way without their consent. I request that you remove or disable access to the URLs listed below, remove known "
            "identical copies, and preserve related records. Where the content is synthetic, please also confirm whether it carries the "
            "label and permanent identifier the Rules require.", body),
            _p("The timeline depends on what starts the request: a court order or government notice (3 hours), a complaint by an individual "
               "about high-risk content such as nudity, intimate imagery, impersonation or morphed images (2 hours), or another complaint by an "
               "individual (36 hours). A victim's own complaint about intimate or morphed imagery is normally the second kind, not the first. "
               "These figures come from published summaries of the 2026 amendments; confirm the timeline that applies to this notice, and "
               "what starts the clock, with counsel before relying on any deadline.", body)]
    elif regime == "tida":
        story += [_p("1. Removal request", st["Heading2"]), _p(
            "I request removal of the intimate visual depiction at the locations listed below, and of known identical copies. I have a "
            "good-faith belief that the depiction was published without my consent (or without the consent of the person I am "
            "authorised to act for). This includes a depiction that is a digital forgery.", body),
            _p("Scope: this pack is for non-consensual INTIMATE imagery only (including intimate depictions that are digital forgeries). "
               "It is not a route for other harmful synthetic media, such as fraud or impersonation without intimate content. It is a US "
               "law: it applies to covered platforms. Under the Act a covered platform that receives a valid request must remove the "
               "depiction and known identical copies within 48 hours; that duty has been enforceable since 19 May 2026 (confirm with counsel).", body),
            _p("Required elements (confirm against the statute text with counsel): signature (physical or electronic) of the person or "
               "their authorised representative; identification of the content and information reasonably sufficient to locate it; "
               "a brief statement of the good-faith belief that the depiction is not consensual; and contact information.", body)]
    else:
        story += [_p("1. How to use this summary", st["Heading2"]), _p(
            "Copy the facts below into the complaint form on cybercrime.gov.in (report under the category for crimes relating to women "
            "or children where it applies) and attach the evidence listed. Keep a copy and the acknowledgement number. The 1930 helpline "
            "is for financial fraud; it is not the route for this kind of complaint. If anyone is in immediate danger, contact local "
            "emergency services.", body)]

    story += [Spacer(1, 6), _p("2. Content and locations", st["Heading2"])]
    urls = [s for s in sources if getattr(s, "url", None)]
    if urls:
        rows = [["Platform", "URL", "Observed (UTC)"]] + [[s.platform or "", s.url, str(s.observed_at or "")] for s in urls]
        story.append(_table(rows, [90, 330, 100]))
    else:
        story.append(_p("No source URLs have been recorded in the case yet. Add the exact URLs before sending.", body))

    story += [Spacer(1, 6), _p("3. Files and fingerprints (SHA-256)", st["Heading2"])]
    rows = [["Artifact", "SHA-256", "Recorded (UTC)"]]
    for m in media:
        rows.append([m.original_filename, m.sha256 or "Not recorded", str(getattr(m, "uploaded_at", ""))])
    for e in evidence:
        rows.append([f"Evidence: {e.item_type}", e.sha256 or "Not recorded", str(getattr(e, "captured_at", ""))])
    for s in sources:
        if getattr(s, "page_sha256", None):
            rows.append([f"Captured page: {s.platform}", s.page_sha256, str(getattr(s, "observed_at", ""))])
    story.append(_table(rows, [150, 270, 100]) if len(rows) > 1 else _p("No hashed artifacts recorded.", body))

    if regime in ("preservation", "it_rules", "ncrp"):
        story += [Spacer(1, 6), _p("4. Hosting information observed", st["Heading2"])]
        if footprints:
            for fp in footprints:
                story.append(_p(f"{fp.get('domain', '-')}: server IP {', '.join(fp.get('server_ips') or []) or 'not resolved'} "
                                f"({fp.get('label', 'Hosting server, not the creator')})", body))
        else:
            story.append(_p("None recorded.", body))
        story.append(_p("Hosting details describe the server only. They do not identify the person who created or uploaded the content; "
                        "that information is held by the platform.", st["Italic"]))

    story += [Spacer(1, 6), _p("5. Requester", st["Heading2"]),
              _p(f"Name: {requester.get('name', '____________________')}\nContact: {requester.get('contact', '____________________')}\n"
                 f"Relationship to the person depicted: {requester.get('relationship', '____________________')}", body),
              Spacer(1, 12), _p("Signature: ______________________      Date: ______________", body)]
    if extra_notes:
        story += [Spacer(1, 6), _p("Additional notes", st["Heading2"]), _p(extra_notes[:2000], body)]
    story += [Spacer(1, 10), _p("Evidence status: investigator support document, not proof. Review all records before sending. "
                                "Prepared with LINEAGE; the hashes above can be checked against the signed manifest.", st["Italic"])]
    doc.build(story)
    return buf.getvalue()


def _table(rows, widths) -> Table:
    cell = getSampleStyleSheet()["BodyText"]
    cell.fontSize = 7
    cell.leading = 9
    data = [[Paragraph(escape(str(c)), cell) for c in r] for r in rows]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F3A5F")), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                           ("GRID", (0, 0), (-1, -1), .25, colors.grey), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    return t
