"""
Content-origin report: where might this content have come from, and what can and cannot be said about it?

Layers (each carries its own reliability note; layers with no data say so instead of guessing):
  1 file        device, software, capture time and GPS read from the file
  2 provenance  Content Credentials (C2PA) and AI-generation markers the file claims
  3 tamper      the metadata-change verdict
  4 hosting     server IP / network / registrar of pages the content was traced to (never the creator)
  5 platform    the only place an uploader's IP address exists: the platform's own logs, obtained through a legal request

There is deliberately NO field that holds a "creator IP". The honest answer to "which IP generated this?" is in `creator_ip`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.services import exif_gps, metadata_forensics, provenance

CREATOR_IP = {
    "available": False,
    "reason": ("An IP address is not stored inside an image or video file. The IP used to upload or create content is held in the "
               "logs of the platform or service that received it."),
    "how_to_obtain": ("Send the platform a preservation request first (so logs are kept), then a disclosure request through the "
                      "legal process that applies (court or police order). The Request Pack and the legal packs in this app prepare both."),
}


def analyse_media(raw: bytes, filename: str | None, *, uploaded_at: datetime | None = None, lang: str = "en",
                  date_gap_seconds: int = metadata_forensics.DATE_GAP_SECONDS, now: datetime | None = None) -> dict[str, Any]:
    """Everything the file itself can tell us. Safe on any bytes."""
    report = metadata_forensics.analyze(raw, filename, uploaded_at=uploaded_at, now=now, date_gap_seconds=date_gap_seconds)
    c2pa = provenance.inspect_c2pa(raw)
    ai = provenance.ai_markers(raw)
    gps = exif_gps.extract_gps(raw) if report.get("supported") else None
    f = report.get("fields", {})
    # A Content-Credentials edit history is an independent signal; fold it into the tamper verdict (it cannot lower it).
    if c2pa["present"] and any(a in c2pa["actions"] for a in ("c2pa.edited", "c2pa.cropped", "c2pa.filtered", "c2pa.color_adjustments", "c2pa.placed")):
        report["findings"].append({"id": "T8", "category": "history", "title": "Content Credentials record edits", "severity": "medium",
                                   "evidence": {"actions": c2pa["actions"], "signature": c2pa["validation"]["status"]},
                                   "caveat": "Credentials list what tools reported; unless the signature validates, they are a claim like any other metadata."})
        cats = sorted({x["category"] for x in report["findings"] if metadata_forensics.SEVERITY_ORDER[x["severity"]] >= 2})
        report["signal_categories"] = cats
        if report["verdict"] in ("no_signals", "cannot_judge") and cats:
            report["verdict"] = "inconsistent_single"
        elif len(cats) >= 2:
            report["verdict"] = "inconsistent_multiple"
    report["description"] = metadata_forensics.describe(report, lang)
    return {
        "file": {"device": " ".join(x for x in (f.get("make"), f.get("model")) if x) or None, "software": f.get("software"),
                 "captured_at": f.get("datetime_original"), "gps": gps,
                 "reliability": "Low to medium: every field can be edited, copied or invented. Most platforms remove them.",
                 "metadata_stripped": not (f.get("has_exif") or f.get("has_xmp") or f.get("has_png_text"))},
        "provenance": {"c2pa": c2pa, "ai_markers": ai,
                       "reliability": "Medium only if a Content Credentials signature validates. Absence proves nothing."},
        "tamper": report,
    }


def build_case(media: list[dict[str, Any]], hosting: list[dict[str, Any]], *, legal_review_status: str = "pending") -> dict[str, Any]:
    """media: [{media_id, filename, analysis}] from analyse_media; hosting: footprint dicts (optionally enriched)."""
    signals: list[str] = []
    for m in media:
        a = m.get("analysis") or {}
        t = (a.get("tamper") or {}).get("verdict")
        if t in ("inconsistent_single", "inconsistent_multiple"):
            signals.append(f"{m.get('filename')}: metadata verdict '{t}'.")
        if (a.get("provenance") or {}).get("ai_markers"):
            signals.append(f"{m.get('filename')}: the file itself states AI generation ({len(a['provenance']['ai_markers'])} marker(s)).")
        if (a.get("file") or {}).get("gps"):
            signals.append(f"{m.get('filename')}: contains GPS coordinates (self-reported by the device).")
    return {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "creator_ip": CREATOR_IP,
        "layers": {
            "file": [{"media_id": m.get("media_id"), "filename": m.get("filename"), **(m.get("analysis") or {}).get("file", {})} for m in media],
            "provenance": [{"media_id": m.get("media_id"), "filename": m.get("filename"), **(m.get("analysis") or {}).get("provenance", {})} for m in media],
            "tamper": [{"media_id": m.get("media_id"), "filename": m.get("filename"), "verdict": ((m.get("analysis") or {}).get("tamper") or {}).get("verdict"),
                        "description": ((m.get("analysis") or {}).get("tamper") or {}).get("description")} for m in media],
            "hosting": [{**h, "label": "Hosting server, not the creator"} for h in hosting],
            "platform": {"status": "not_requested_by_this_app",
                         "note": "Only the platform can supply uploader IP, account and login history. Generate a preservation + disclosure request from the legal pack endpoint.",
                         "legal_review_status": legal_review_status},
        },
        "signals_found": signals,
        "limits": ["Signals are not proof of who made or changed anything.",
                   "A layer with no data means the information is not available, not that the content is genuine or fake."],
    }
