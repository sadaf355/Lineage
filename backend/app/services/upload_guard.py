"""Glue between upload_sniff and the upload endpoints: sniff, audit, and refuse with HTTP 415."""
from __future__ import annotations

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.services import audit, upload_scan, upload_sniff


def _record(db: Session, incident_id: str, user, action: str, filename: str | None, claimed: str, res) -> None:
    audit.record(db, incident_id, user, action, target_type="upload", details={
        "filename": (filename or "")[:200], "claimed": claimed, "detected": res.detected, "reason": res.reason,
    }, commit=True)


def guard_media_upload(db: Session, incident_id: str, user, fileobj, filename: str | None, claimed_kind: str) -> upload_sniff.SniffResult:
    s = get_settings()
    if (s.UPLOAD_SNIFF_MODE or "enforce").lower() == "off":
        return upload_sniff.SniffResult(True, None, False, "content sniffing disabled")
    res = upload_sniff.sniff_media(upload_sniff.read_head(fileobj), claimed_kind, filename,
                                   mode=s.UPLOAD_SNIFF_MODE, strict_av=s.UPLOAD_SNIFF_STRICT_AV)
    return _apply(db, incident_id, user, filename, claimed_kind, res)


def guard_evidence_upload(db: Session, incident_id: str, user, fileobj, filename: str | None) -> upload_sniff.SniffResult:
    s = get_settings()
    if (s.UPLOAD_SNIFF_MODE or "enforce").lower() == "off":
        return upload_sniff.SniffResult(True, None, False, "content sniffing disabled")
    res = upload_sniff.sniff_evidence(upload_sniff.read_head(fileobj), filename, mode=s.UPLOAD_SNIFF_MODE)
    return _apply(db, incident_id, user, filename, "evidence", res)


def scan_upload(db: Session, incident_id: str, user, fileobj, filename: str | None, claimed: str) -> None:
    """Malware / pixel-bomb screen. MALWARE_SCAN_MODE: off (default) | log | enforce.
    In enforce mode a hit, or an unreachable scanner, refuses the upload (HTTP 422 / 503)."""
    s = get_settings()
    mode = (s.MALWARE_SCAN_MODE or "off").lower()
    if mode == "off":
        return
    res = upload_scan.scan_stream(fileobj, mode=mode, max_pixels=s.MAX_IMAGE_PIXELS, max_bytes=s.MAX_UPLOAD_MB * 1024 * 1024 + 1,
                                  clamd_host=s.CLAMD_HOST, clamd_port=s.CLAMD_PORT, clamd_timeout=s.CLAMD_TIMEOUT_SECONDS)
    unavailable = res.ok and res.reason == "clamd unavailable"
    if res.ok and not unavailable:
        return
    audit.record(db, incident_id, user, "upload_rejected", target_type="upload", details={
        "filename": (filename or "")[:200], "claimed": claimed, "engine": res.engine,
        "reason": res.reason, "mode": mode}, commit=True)
    if mode == "enforce":
        if unavailable:
            raise HTTPException(status_code=503, detail="Upload scanner unavailable; try again shortly.")
        raise HTTPException(status_code=422, detail=f"Upload refused by scanner: {res.reason}")


def _apply(db, incident_id, user, filename, claimed, res):
    if not res.ok:
        _record(db, incident_id, user, "upload_rejected", filename, claimed, res)
        raise HTTPException(status_code=415, detail=f"Upload refused: {res.reason}")
    if res.would_reject:
        _record(db, incident_id, user, "upload_rejected", filename, claimed, res)  # log mode: recorded, not refused
    elif not res.verified and claimed in ("video", "audio"):
        _record(db, incident_id, user, "upload_unverified", filename, claimed, res)
    return res
