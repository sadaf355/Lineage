"""
Metadata-change detection, content-origin report, legal packs and signed case bundle.

GET  /incidents/{id}/media/{mid}/metadata-report   ?lang=en|hi   has the metadata been changed since capture? (signals + caveats)
GET  /incidents/{id}/origin                        ?lang=en|hi   layered origin report (never a creator IP)
POST /incidents/{id}/automation/legal-pack                       PDF draft: preservation | it_rules | tida | ncrp
GET  /incidents/{id}/audit/verify                 recompute the tamper-evident audit chain
GET  /incidents/{id}/evidence/bundle               ?include_files=false   signed zip for police / platform / court
Nothing here sends anything outside LINEAGE, except the optional RDAP hosting lookup (off by default).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.media import MediaItem, MetadataSnapshot
from app.services import metadata_snapshots
from app.models.phase56 import SignedManifest
from app.models.source import EvidenceItem, Source
from app.models.report import IncidentReport
from app.schemas.report import IncidentReportPayload
from app.services.report_pdf import render_report_pdf
from app.models.user import User
from app.routers.incidents import _get_owned_incident
from app.services import audit, case_bundle, file_storage, footprints, hosting_enrich, legal_packs, origin, redis_rate_limit

settings = get_settings()
router = APIRouter(prefix="/incidents", tags=["origin"])
MAX_BUNDLE_BYTES = 200 * 1024 * 1024


def _rate_limit(user: User, bucket: str, per_minute: int = 30) -> None:
    if not redis_rate_limit.allow(f"{bucket}:{user.id}", per_minute):
        raise HTTPException(status_code=429, detail="Too many requests. Please wait a minute.")


def _get_media(db: Session, incident_id: str, media_id: str) -> MediaItem:
    m = db.query(MediaItem).filter(MediaItem.id == media_id, MediaItem.incident_id == incident_id).first()
    if not m:
        raise HTTPException(status_code=404, detail="Media not found.")
    return m


def _analyse(m: MediaItem, lang: str) -> dict:
    if m.kind != "image":
        return {"supported": False, "note": f"Metadata analysis currently covers images only; this item is {m.kind}.",
                "tamper": {"verdict": "cannot_judge", "reason": "unsupported_media_kind", "findings": [], "limits": []}}
    try:
        raw = file_storage.read_decrypted(m.storage_path)
    except Exception:
        raise HTTPException(status_code=500, detail="The stored file could not be read.")
    return origin.analyse_media(raw, m.original_filename, uploaded_at=m.uploaded_at, lang=lang,
                                date_gap_seconds=settings.METADATA_DATE_GAP_SECONDS)


@router.get("/{incident_id}/media/{media_id}/metadata-report")
def metadata_report(incident_id: str, media_id: str, lang: Literal["en", "hi"] = "en",
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    _rate_limit(current_user, "metadata")
    m = _get_media(db, inc.id, media_id)
    return {"media_id": m.id, "filename": m.original_filename, "sha256": m.sha256, **_analyse(m, lang)}




C2PA_BUNDLE_MAX_BYTES = 50 * 1024 * 1024


def _c2pa_for_bundle(m: MediaItem) -> dict:
    """Real structural read (and signature check when the optional c2pa package is installed). Never raises."""
    from app.services import provenance
    if (m.file_size_bytes or 0) > C2PA_BUNDLE_MAX_BYTES:
        return {"state": "not_validated", "present": None, "note": "File is larger than the 50 MB limit for this check; no authenticity claim is made."}
    try:
        with file_storage.decrypted_tempfile(m.storage_path) as plain_path:
            with open(plain_path, "rb") as fh:
                raw = fh.read(C2PA_BUNDLE_MAX_BYTES + 1)
        res = provenance.inspect_c2pa(raw)
        return {"state": (res.get("validation") or {}).get("status", "not_validated"), **res}
    except Exception as exc:  # noqa: BLE001 - the bundle must still build
        return {"state": "error", "present": None, "note": f"Could not read Content Credentials ({type(exc).__name__}); no authenticity claim is made."}


@router.post("/{incident_id}/media/{media_id}/metadata/compare")
async def compare_metadata(incident_id: str, media_id: str, file: UploadFile | None = File(default=None), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    m = _get_media(db, inc.id, media_id)
    previous = db.query(MetadataSnapshot).filter(MetadataSnapshot.media_item_id == m.id).order_by(MetadataSnapshot.taken_at.asc()).first()
    # A caller may supply a later copy. Without one, this re-checks the preserved bytes and cannot claim a change.
    if file is not None:
        raw = await file.read(4 * 1024 * 1024 + 1)  # only the header is parsed; never read an unbounded body
    else:
        with file_storage.decrypted_tempfile(m.storage_path) as plain_path:
            with open(plain_path, "rb") as plain:
                raw = plain.read(4 * 1024 * 1024)
    _, normalized = metadata_snapshots.parse_metadata(raw, file.filename if file is not None else m.original_filename)
    result = metadata_snapshots.compare_snapshots(previous, normalized)
    if file is None and result.get("state") == "changed against snapshot":
        result = {"state":"unknown", "reason":"No later copy was supplied; the preserved original is not evidence of a subsequent change."}
    return {"media_id": m.id, "snapshot_id": previous.id if previous else None, "recheck_source":"uploaded_copy" if file is not None else "preserved_original", **result}

@router.get("/{incident_id}/origin")
def origin_report(incident_id: str, lang: Literal["en", "hi"] = "en",
                  db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    _rate_limit(current_user, "origin", 12)
    media = []
    for m in db.query(MediaItem).filter(MediaItem.incident_id == inc.id).order_by(MediaItem.uploaded_at).all():
        media.append({"media_id": m.id, "filename": m.original_filename, "analysis": _analyse(m, lang)})
    sources = db.query(Source).filter(Source.incident_id == inc.id).all()
    hosting = [hosting_enrich.enrich(footprints.hosting_footprint(s.url), enabled=settings.HOSTING_RDAP_ENABLED,
                                     base=settings.HOSTING_RDAP_BASE, timeout=settings.HOSTING_RDAP_TIMEOUT_SECONDS)
               for s in sources if s.url][:25]
    return origin.build_case(media, hosting, legal_review_status=settings.LEGAL_REVIEW_STATUS)


class LegalPackIn(BaseModel):
    regime: Literal["preservation", "it_rules", "tida", "ncrp"]
    platform: str | None = Field(default=None, max_length=200)
    requester_name: str | None = Field(default=None, max_length=200)
    requester_contact: str | None = Field(default=None, max_length=300)
    requester_relationship: str | None = Field(default=None, max_length=200)
    order_received_at: datetime | None = None
    # it_rules only: what started the request, which sets the planning deadline (3 h order, 2 h high-risk complaint, 36 h other complaint).
    track: Literal["order", "high_risk_complaint", "individual_complaint"] | None = None
    notes: str | None = Field(default=None, max_length=2000)


@router.post("/{incident_id}/automation/legal-pack")
def legal_pack(incident_id: str, payload: LegalPackIn, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    _rate_limit(current_user, "legalpack", 10)
    media = db.query(MediaItem).filter(MediaItem.incident_id == inc.id).all()
    sources = db.query(Source).filter(Source.incident_id == inc.id).all()
    evidence = db.query(EvidenceItem).filter(EvidenceItem.incident_id == inc.id).all()
    fps = [hosting_enrich.enrich(footprints.hosting_footprint(s.url), enabled=settings.HOSTING_RDAP_ENABLED,
                                 base=settings.HOSTING_RDAP_BASE, timeout=settings.HOSTING_RDAP_TIMEOUT_SECONDS)
           for s in sources if s.url][:25]
    status = settings.LEGAL_REVIEW_STATUS
    if settings.LEGAL_REVIEWED_TEMPLATE_VERSION != legal_packs.TEMPLATE_VERSION and status == "approved":
        status = "pending"          # approval only counts for the template version counsel actually reviewed
    pdf = legal_packs.build_pack(
        payload.regime, incident=inc, media=media, sources=sources, evidence=evidence, footprints=fps,
        requester={k: v for k, v in (("name", payload.requester_name), ("contact", payload.requester_contact),
                                     ("relationship", payload.requester_relationship)) if v},
        platform=payload.platform, order_received_at=payload.order_received_at, legal_review_status=status, extra_notes=payload.notes or "", track=payload.track)
    audit.record(db, inc.id, current_user, "legal_pack_generated", target_type="legal_pack",
                 details={"regime": payload.regime, "template": legal_packs.TEMPLATE_VERSION, "legal_review_status": status})
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="lineage-{payload.regime}-{inc.id[:8]}.pdf"'})


@router.get("/{incident_id}/audit/verify")
def audit_verify(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Recompute the audit hash chain for this case and report the first break, if any."""
    inc = _get_owned_incident(incident_id, db, current_user)
    return {"investigation_id": inc.id, **audit.verify_chain(db, inc.id)}


@router.get("/{incident_id}/evidence/bundle")
def evidence_bundle(incident_id: str, include_files: bool = Query(False, description="Include the original files. They are sensitive: only when the recipient needs them."),
                    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    _rate_limit(current_user, "bundle", 6)
    media = db.query(MediaItem).filter(MediaItem.incident_id == inc.id).all()
    evidence = db.query(EvidenceItem).filter(EvidenceItem.incident_id == inc.id).all()
    sources = db.query(Source).filter(Source.incident_id == inc.id).all()
    rows = [{"name": m.original_filename, "kind": f"media/{m.kind}", "sha256": m.sha256, "recorded_at": str(m.uploaded_at)} for m in media]
    snapshot_artifacts = []
    for m in media:
        snap = db.query(MetadataSnapshot).filter(MetadataSnapshot.media_item_id == m.id).order_by(MetadataSnapshot.taken_at.desc()).first()
        if snap:
            snapshot_payload = {"snapshot_id": snap.id, "media_id": m.id, "parser": snap.parser_name, "parser_version": snap.parser_version, "file_sha256": snap.file_sha256, "raw_fields": json.loads(snap.raw_fields_json), "normalized_fields": json.loads(snap.normalized_fields_json), "snapshot_sha256": snap.snapshot_sha256, "taken_at": snap.taken_at.isoformat() + "Z"}
            snapshot_artifacts.append((f"metadata_snapshot_{m.id}.json", json.dumps(snapshot_payload, indent=2, sort_keys=True).encode()))
            rows.append({"name": f"metadata_snapshot_{m.id}.json", "kind": "metadata_snapshot", "sha256": snap.snapshot_sha256, "recorded_at": str(snap.taken_at)})
    c2pa_artifact = ("c2pa_results.json", json.dumps({m.id: _c2pa_for_bundle(m) for m in media}, indent=2, sort_keys=True, default=str).encode())
    report_row = db.query(IncidentReport).filter(IncidentReport.incident_id == inc.id).first()
    report_pdf = None
    if report_row:
        report_payload = IncidentReportPayload(**json.loads(report_row.report_json))
        report_pdf = render_report_pdf(report_payload, inc.title, inc.id, manifest=[{"label":m.original_filename,"sha256":m.sha256,"captured_at":str(m.uploaded_at)} for m in media if m.sha256], language="en")
    timestamp_artifact = ("bundle_timestamp.json", json.dumps({"generated_at": datetime.utcnow().isoformat()+"Z", "timestamp_authority_token": None, "note":"Bundle generation time only; no RFC 3161 token is asserted."}, indent=2).encode())
    rows += [{"name": f"evidence:{e.item_type}", "kind": "evidence", "sha256": e.sha256, "recorded_at": str(e.captured_at)} for e in evidence]
    rows += [{"name": f"page:{s.platform}", "kind": "captured_page", "sha256": s.page_sha256, "recorded_at": str(s.observed_at)} for s in sources if s.page_sha256]
    files: list[tuple[str, bytes]] | None = None
    if include_files:
        files, total = [], 0
        for label, path in [(m.original_filename, m.storage_path) for m in media] + [(f"evidence_{e.id[:8]}_{e.item_type}", e.storage_path) for e in evidence if e.storage_path]:
            try:
                data = file_storage.read_decrypted(path)
            except Exception:
                continue
            total += len(data)
            if total > MAX_BUNDLE_BYTES:
                raise HTTPException(status_code=413, detail="The files are too large for one bundle. Export without files and send them separately.")
            files.append((label, data))
    latest = db.query(SignedManifest).filter(SignedManifest.incident_id == inc.id).order_by(SignedManifest.created_at.desc()).first()
    envelope = json.loads(latest.envelope_json) if latest else None
    verifier = None
    vp = Path(__file__).resolve().parents[3] / "scripts" / "verify_manifest.py"
    if vp.exists():
        verifier = vp.read_text(encoding="utf-8")
    extra_bundle_entries = snapshot_artifacts + [c2pa_artifact, timestamp_artifact]
    data = case_bundle.build_bundle(incident_id=inc.id, title=inc.title, evidence_rows=rows, manifest_envelope=envelope,
                                    files=files, extra_entries=extra_bundle_entries, verifier_source=verifier,
                                    include_report_pdf=report_pdf,
                                    custody_log={"events": audit.list_events(db, inc.id), "chain": audit.export_chain(db, inc.id),
                                                 "chain_check": audit.verify_chain(db, inc.id)},
                                    audit_anchor=audit.anchor(db, inc.id), include_original_files=include_files)
    audit.record(db, inc.id, current_user, "case_bundle_exported", target_type="bundle",
                 details={"include_files": include_files, "signed_manifest": bool(envelope), "entries": len(rows)})
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="lineage-bundle-{inc.id[:8]}.zip"'})
