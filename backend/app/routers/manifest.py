"""Phase E: signed integrity manifests (Ed25519) with an optional RFC 3161 trusted timestamp."""
from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.media import MediaItem
from app.models.phase56 import SignedManifest
from app.models.source import EvidenceItem, Source
from app.models.user import User
from app.routers.incidents import _get_owned_incident
from app.services import audit, manifest as mf

settings = get_settings()
router = APIRouter(tags=["manifest"])


def _current_entries(db: Session, incident_id: str) -> list[dict]:
    return mf.build_entries(
        db.query(MediaItem).filter(MediaItem.incident_id == incident_id).all(),
        db.query(EvidenceItem).filter(EvidenceItem.incident_id == incident_id).all(),
        db.query(Source).filter(Source.incident_id == incident_id).all(),
    )


def _signing_key():
    try:
        return mf.load_signing_key()
    except mf.ManifestError as exc:
        raise HTTPException(status_code=503, detail=f"Manifest signing is not configured: {exc}")


@router.get("/trust/manifest-key")
def manifest_public_key():
    """Public by design: the verification key must be obtainable without an account. Publish the key_id on reports."""
    return mf.public_key_info(_signing_key())


@router.post("/incidents/{incident_id}/evidence/manifest", status_code=201)
def create_manifest(
    incident_id: str,
    timestamp: bool = Query(False, description="Also request an RFC 3161 timestamp (needs MANIFEST_TSA_URL)."),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inc = _get_owned_incident(incident_id, db, current_user)
    if timestamp and not settings.MANIFEST_TSA_URL:
        raise HTTPException(status_code=409, detail="No Time-Stamp Authority is configured (MANIFEST_TSA_URL).")
    key = _signing_key()
    envelope = mf.sign_manifest(mf.build_manifest(inc.id, _current_entries(db, inc.id), audit_anchor=audit.anchor(db, inc.id)), key)
    if timestamp:
        mf.attach_timestamp(envelope, settings.MANIFEST_TSA_URL, settings.MANIFEST_TSA_TIMEOUT_SECONDS)
    row = SignedManifest(
        incident_id=inc.id, generated_by=current_user.id, key_id=envelope["signature"]["key_id"],
        manifest_sha256=envelope["manifest_sha256"], envelope_json=json.dumps(envelope), has_timestamp=bool(envelope.get("timestamp")),
    )
    db.add(row)
    audit.record(db, inc.id, current_user, "manifest_signed", target_type="manifest", target_id=row.id,
                 details={"key_id": row.key_id, "entries": envelope["manifest"]["entry_count"], "timestamped": row.has_timestamp}, commit=False)
    db.commit(); db.refresh(row)
    return {"id": row.id, "created_at": row.created_at, **envelope}


@router.get("/incidents/{incident_id}/evidence/manifests")
def list_manifests(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    rows = db.query(SignedManifest).filter(SignedManifest.incident_id == inc.id).order_by(SignedManifest.created_at.desc()).all()
    return [{"id": r.id, "key_id": r.key_id, "manifest_sha256": r.manifest_sha256, "has_timestamp": r.has_timestamp, "created_at": r.created_at} for r in rows]


def _get_row(db: Session, incident_id: str, manifest_id: str) -> SignedManifest:
    row = db.query(SignedManifest).filter(SignedManifest.id == manifest_id, SignedManifest.incident_id == incident_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Manifest not found.")
    return row


@router.get("/incidents/{incident_id}/evidence/manifests/{manifest_id}")
def get_manifest(incident_id: str, manifest_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    row = _get_row(db, inc.id, manifest_id)
    return {"id": row.id, "created_at": row.created_at, **json.loads(row.envelope_json)}


@router.post("/incidents/{incident_id}/evidence/manifests/{manifest_id}/verify")
def verify_manifest(incident_id: str, manifest_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Verify against THIS deployment's key (not the envelope's own), then report drift since signing."""
    inc = _get_owned_incident(incident_id, db, current_user)
    row = _get_row(db, inc.id, manifest_id)
    envelope = json.loads(row.envelope_json)
    trusted = mf.public_key_info(_signing_key())["public_key"]
    result = mf.verify_envelope(envelope, trusted)
    drift = mf.diff_against_current(envelope["manifest"], _current_entries(db, inc.id))
    anchored = envelope["manifest"].get("audit_anchor")
    audit_check = None
    if anchored and anchored.get("head_hash"):
        from app.services import audit_chain
        r = audit_chain.check_against_anchor(audit.export_chain(db, inc.id), anchored)
        audit_check = {"anchored_head_seq": anchored.get("head_seq"), "chain_ok_now": r["ok"], "anchor_found_in_current_log": r["anchor_ok"],
                       "reason": r.get("reason")}
    audit.record(db, inc.id, current_user, "manifest_verified", target_type="manifest", target_id=row.id,
                 details={"signature_valid": result["signature_valid"], "unchanged": drift["unchanged"]})
    return {"id": row.id, "verification": result, "timestamp": mf.check_timestamp(envelope), "case_drift_since_signing": drift,
            "audit_anchor_check": audit_check,
            "note": "Drift is expected when evidence is added after signing; it does not invalidate the signature."}
