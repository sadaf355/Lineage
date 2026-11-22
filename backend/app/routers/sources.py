from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
from datetime import datetime
from pathlib import Path
import hashlib

from app.core.config import get_settings

from app.db.session import get_db
from app.deps import get_current_user
from app.models.source import Source, SourceRelationship, EvidenceItem
from app.models.media import MediaItem
from app.services import file_storage, source_tracing
from app.models.user import User
from app.schemas.source import SourceCreate, SourceOut, SourceRelationshipCreate, SourceRelationshipOut
from app.routers.incidents import _get_owned_incident
from app.services import audit, abuse_guard
from app.services.operations import record_operational_event
from app.services import redis_rate_limit

router = APIRouter(prefix="/incidents", tags=["sources"])
settings = get_settings()


def _validate_trace_storage_path(storage_path: str) -> Path:
    """Only allow traced page captures inside the configured uploads directory."""
    base = Path(settings.UPLOADS_DIR).resolve()
    candidate = Path(storage_path).resolve()
    try:
        candidate.relative_to(base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid captured source storage path.")
    return candidate



@router.get("/{incident_id}/sources", response_model=list[SourceOut])
def list_sources(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    return db.query(Source).filter(Source.incident_id == incident.id).order_by(Source.observed_at).all()


@router.post("/{incident_id}/sources", response_model=SourceOut, status_code=201)
def add_source(
    incident_id: str,
    payload: SourceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    source = Source(incident_id=incident.id, **payload.model_dump())
    db.add(source)
    if incident.status in ("created", "analyzing", "fingerprinted"):
        incident.status = "evidence_building"
    db.commit()
    db.refresh(source)
    return source


@router.post("/{incident_id}/sources/relationships", response_model=SourceRelationshipOut, status_code=201)
def add_relationship(
    incident_id: str,
    payload: SourceRelationshipCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)

    valid_ids = {s.id for s in db.query(Source).filter(Source.incident_id == incident.id).all()}
    if payload.from_source_id not in valid_ids or payload.to_source_id not in valid_ids:
        raise HTTPException(status_code=400, detail="Both sources must belong to this incident.")

    rel = SourceRelationship(**payload.model_dump())
    db.add(rel)
    db.commit()
    db.refresh(rel)
    return rel


@router.get("/{incident_id}/sources/relationships", response_model=list[SourceRelationshipOut])
def list_relationships(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    source_ids = [s.id for s in db.query(Source).filter(Source.incident_id == incident.id).all()]
    if not source_ids:
        return []
    return (
        db.query(SourceRelationship)
        .filter(SourceRelationship.from_source_id.in_(source_ids))
        .all()
    )


@router.post("/{incident_id}/sources/trace-url")
def trace_source_url(
    incident_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify a pasted public URL and return a reviewable match candidate."""
    incident = _get_owned_incident(incident_id, db, current_user)
    url = str(payload.get("url") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="A URL is required.")
    if not redis_rate_limit.allow(f"trace:{current_user.id}:{incident.id}", settings.RATE_LIMIT_TRACE_PER_MINUTE):
        raise HTTPException(status_code=429, detail="URL tracing rate limit reached. Please wait before trying again.")
    media_items = db.query(MediaItem).filter(MediaItem.incident_id == incident.id).order_by(MediaItem.uploaded_at).all()
    if not media_items:
        raise HTTPException(status_code=400, detail="Upload case media before tracing a source URL.")
    case_images=[]
    for media in media_items:
        if media.kind != "image":
            continue
        try:
            case_images.append((media.id, file_storage.read_decrypted(media.storage_path)))
        except Exception:
            continue
    if not case_images:
        raise HTTPException(status_code=400, detail="URL tracing currently requires at least one image in the case.")
    audit.record(db, incident.id, current_user, "source_trace_requested", target_type="incident", target_id=incident.id, details={"url": url}, commit=False)
    try:
        result=source_tracing.trace_url(url, case_images)
    except Exception as exc:
        message = str(exc)
        if any(term in message.lower() for term in ("private", "reserved", "public http", "public address", "resolve")):
            record_operational_event(db, "ssrf_refusal", message, current_user.id)
            db.commit()
        raise HTTPException(status_code=422, detail=f"Could not inspect that URL: {exc}")
    if not result.matches:
        db.commit()
        return {"matched": False, "source": None, "matches": [], "message": "No image matched the case media: neither two agreeing perceptual hashes at ≥85% nor a geometrically verified local-feature match."}
    best=result.matches[0]
    page_storage_path, _ = file_storage.save_encrypted(result.html, "source-page.html")
    db.commit()
    pending = {
        "url": result.url, "platform": result.platform, "observed_at": result.captured_at.isoformat(),
        "similarity_score": best.similarity, "method": best.method, "agreeing_hashes": best.agreeing_hashes,
        "page_sha256": result.page_sha256, "page_storage_path": page_storage_path, "matched_image_url": best.url,
        "issued_at": int(time.time()),
    }
    pending["signature"] = source_tracing.sign_pending_match(pending, incident.id)
    return {
        "matched": True,
        "source": None,
        "matches": [m.__dict__ for m in result.matches],
        "pending_match": pending,
        "message": "Potential match found. Review the evidence and explicitly accept it before it becomes a source."
    }


@router.post("/{incident_id}/sources/trace-url/accept", response_model=SourceOut, status_code=201)
def accept_traced_source(incident_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = _get_owned_incident(incident_id, db, current_user)
    review = abuse_guard.review_required("trace_accept")
    if not review.allowed and not bool(payload.get("review_confirmed")):
        raise HTTPException(status_code=428, detail=review.reason + " Set review_confirmed=true only after inspecting the candidate evidence.")
    try:
        source_tracing.validate_trace_accept_payload(payload)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        source_tracing.verify_pending_match(payload, incident.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    try:
        observed_at = datetime.fromisoformat(str(payload["observed_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid observed_at timestamp.")

    # Never trust the client to choose an arbitrary encrypted path. The pending
    # path came from this server's trace step, and the captured bytes must still
    # match the immutable page digest before they can become evidence.
    try:
        page_storage_path = _validate_trace_storage_path(str(payload["page_storage_path"]))
        captured_page = file_storage.read_decrypted(str(page_storage_path))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=400, detail="Captured source page is unavailable or invalid.")
    actual_page_sha256 = hashlib.sha256(captured_page).hexdigest()
    if actual_page_sha256 != str(payload["page_sha256"]):
        raise HTTPException(status_code=409, detail="Captured source page failed integrity verification.")

    source = Source(incident_id=incident.id, platform=str(payload["platform"]), url=str(payload["url"]),
                    observed_at=observed_at, similarity_score=float(payload["similarity_score"]),
                    relationship_label=f"Verified page-image match via {payload.get('method', 'hash ensemble')}; investigator accepted.",
                    is_seeded=False, page_sha256=str(payload["page_sha256"]))
    db.add(source); db.flush()
    db.add(EvidenceItem(incident_id=incident.id, source_id=source.id, item_type="source_page_capture",
                        storage_path=str(page_storage_path),
                        notes=f"Accepted by investigator. Matched image: {payload.get('matched_image_url', '—')}. Hash agreement: {payload.get('agreeing_hashes', '—')}/3.",
                        sha256=str(payload["page_sha256"]), captured_at=source.observed_at))
    audit.record(db, incident.id, current_user, "source_trace_match_reviewed", target_type="source", target_id=source.id,
                 details={"accepted": True, "url": source.url, "similarity": source.similarity_score}, commit=False)
    if incident.status in ("created", "analyzing", "fingerprinted"):
        incident.status = "evidence_building"
    db.commit(); db.refresh(source)
    return source


@router.post("/{incident_id}/sources/trace-url/reject", status_code=204)
def reject_traced_source(incident_id: str, payload: dict, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Dismiss a pending match and delete its temporary encrypted page capture."""
    incident = _get_owned_incident(incident_id, db, current_user)
    try:
        source_tracing.verify_pending_match(payload, incident.id, check_expiry=False)
        page_storage_path = _validate_trace_storage_path(str(payload["page_storage_path"]))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    referenced = db.query(EvidenceItem).filter(EvidenceItem.storage_path == str(page_storage_path)).first()
    if not referenced:
        file_storage.delete_encrypted(str(page_storage_path))
    audit.record(db, incident.id, current_user, "source_trace_match_reviewed", target_type="incident", target_id=incident.id,
                 details={"accepted": False, "url": str(payload.get("url", ""))})
    return Response(status_code=204)
