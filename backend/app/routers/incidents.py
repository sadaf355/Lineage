from fastapi.responses import Response
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.incident import Incident
from app.models.user import User
from app.services import audit, file_storage
from app.models.source import Source, SourceRelationship
from app.models.location import SourceLocation
from app.models.web_search import WebSearchRun
from app.models.automation import AuditEvent, InvestigationReport, AlertDraft
from app.models.operations import CaseTombstone
import json
from datetime import datetime
from app.schemas.incident import IncidentCreate, IncidentOut

router = APIRouter(prefix="/incidents", tags=["incidents"])


def _get_owned_incident(incident_id: str, db: Session, user: User) -> Incident:
    incident = (
        db.query(Incident)
        .filter(Incident.id == incident_id, Incident.owner_id == user.id)
        .first()
    )
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found.")
    return incident


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(
    payload: IncidentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = Incident(
        owner_id=current_user.id,
        title=payload.title,
        description=payload.description,
        victim_ref=payload.victim_ref,
        status="created",
    )
    db.add(incident)
    db.commit()
    db.refresh(incident)
    return incident


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Incident)
        .filter(Incident.owner_id == current_user.id)
        .order_by(Incident.created_at.desc())
        .all()
    )


@router.get("/{incident_id}", response_model=IncidentOut)
def get_incident(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return _get_owned_incident(incident_id, db, current_user)


def _delete_incident_record(incident, db: Session) -> None:
    """Delete an incident and all persisted evidence files using one cleanup path."""
    # Preserve the final custody anchor before the audit rows and evidence are removed.
    chain = audit.verify_chain(db, incident.id)
    head_hash = (audit.anchor(db, incident.id) or {}).get("head_hash")
    deletion_event = {"event": "case_deleted", "case_id": incident.id, "deleted_at": datetime.utcnow().isoformat() + "Z", "final_audit_head_hash": head_hash, "chain_check": chain}
    db.add(CaseTombstone(case_id=incident.id, owner_user_id=incident.owner_id, final_audit_head_hash=head_hash, deletion_event_json=json.dumps(deletion_event, sort_keys=True, default=str)))
    db.flush()
    media_paths = [m.storage_path for m in incident.media_items if m.storage_path]
    evidence_paths = [e.storage_path for e in incident.evidence_items if e.storage_path]
    source_ids = [s.id for s in incident.sources]
    if source_ids:
        db.query(SourceLocation).filter(SourceLocation.source_id.in_(source_ids)).delete(synchronize_session=False)
        db.query(SourceRelationship).filter(
            (SourceRelationship.from_source_id.in_(source_ids)) |
            (SourceRelationship.to_source_id.in_(source_ids))
        ).delete(synchronize_session=False)
    db.query(WebSearchRun).filter(WebSearchRun.incident_id == incident.id).delete(synchronize_session=False)
    db.query(AuditEvent).filter(AuditEvent.incident_id == incident.id).delete(synchronize_session=False)
    db.query(InvestigationReport).filter(InvestigationReport.incident_id == incident.id).delete(synchronize_session=False)
    db.query(AlertDraft).filter(AlertDraft.incident_id == incident.id).delete(synchronize_session=False)
    db.delete(incident)
    db.commit()
    for path in set(media_paths + evidence_paths):
        try:
            file_storage.delete_encrypted(path)
        except Exception:
            pass


@router.delete("/{incident_id}", status_code=204)
def delete_incident(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    incident = _get_owned_incident(incident_id, db, current_user)
    _delete_incident_record(incident, db)
    return Response(status_code=204)
