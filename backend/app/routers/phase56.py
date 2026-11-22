from __future__ import annotations
import json, platform
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.phase56 import BackgroundJob, ConsentRecord, EvidenceCertificate, SignedManifest
from app.models.media import MediaItem
from app.models.source import EvidenceItem
from app.models.user import User
from app.services import consent as consent_service
from app.routers.incidents import _get_owned_incident
from app.services import audit
settings=get_settings()
router=APIRouter(prefix="/incidents",tags=["phase5-6"])

class ConsentIn(BaseModel):
    purpose: str
    granted: bool = True
    details: dict | None = None

    @field_validator("purpose")
    @classmethod
    def _known_purpose(cls, v: str) -> str:
        # A typo'd purpose would be stored but never match the check, silently granting nothing.
        if v not in consent_service.KNOWN_PURPOSES:
            raise ValueError(f"Unknown consent purpose. Use one of: {', '.join(consent_service.KNOWN_PURPOSES)}")
        return v

@router.get("/{incident_id}/jobs/{job_id}")
def job_status(incident_id,job_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    _get_owned_incident(incident_id,db,current_user); j=db.query(BackgroundJob).filter(BackgroundJob.id==job_id,BackgroundJob.incident_id==incident_id).first()
    if not j: raise HTTPException(404,"Job not found")
    return {"id":j.id,"type":j.job_type,"status":j.status,"attempts":j.attempts,"error":j.error,"result":json.loads(j.result_json) if j.result_json else None,"created_at":j.created_at}

@router.post("/{incident_id}/jobs/report",status_code=202)
def queue_report(incident_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    inc=_get_owned_incident(incident_id,db,current_user)
    from app.services.jobs import enqueue, run_job
    j=enqueue(db,job_type="report",payload={"incident_id":inc.id},owner_id=current_user.id,incident_id=inc.id)
    queue_active=bool(settings.JOB_QUEUE_ENABLED and settings.REDIS_URL)
    if not queue_active:
        # No worker is running (the default for local and demo use), so do the work now instead of leaving
        # the job "queued" for a worker that does not exist.
        run_job(db,j); db.refresh(j)
    return {"job_id":j.id,"status":j.status,"worker_required":queue_active,"ran_inline":not queue_active}

@router.post("/{incident_id}/privacy/consent",status_code=201)
def record_consent(incident_id,payload:ConsentIn,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    inc=_get_owned_incident(incident_id,db,current_user)
    row=ConsentRecord(incident_id=inc.id,user_id=current_user.id,purpose=payload.purpose,policy_version=settings.PRIVACY_POLICY_VERSION,granted=payload.granted,details_json=json.dumps(payload.details or {}))
    db.add(row); db.commit(); db.refresh(row)
    return {"id":row.id,"purpose":row.purpose,"granted":row.granted,"policy_version":row.policy_version,"created_at":row.created_at}

@router.get("/{incident_id}/privacy/consents")
def consents(incident_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    inc=_get_owned_incident(incident_id,db,current_user)
    return [{"id":r.id,"purpose":r.purpose,"granted":r.granted,"policy_version":r.policy_version,"created_at":r.created_at} for r in db.query(ConsentRecord).filter(ConsentRecord.incident_id==inc.id).order_by(ConsentRecord.created_at.desc()).all()]


def legal_status_text() -> str:
    """Certificate legal banner. 'Reviewed' only when counsel approved THIS template version; never inferred."""
    approved = settings.LEGAL_REVIEW_STATUS.lower() == "approved" and settings.LEGAL_REVIEWED_TEMPLATE_VERSION == settings.BSA_CERTIFICATE_TEMPLATE_VERSION
    if approved:
        return f"Template v{settings.BSA_CERTIFICATE_TEMPLATE_VERSION} reviewed by counsel. The signer must still complete the statutory declarations; this is not legal advice."
    return "DRAFT — not reviewed by counsel for this template version; not a certification of admissibility or legal advice"

def latest_manifest_reference(db, incident_id: str):
    row = db.query(SignedManifest).filter(SignedManifest.incident_id == incident_id).order_by(SignedManifest.created_at.desc()).first()
    if not row:
        return None
    env = json.loads(row.envelope_json); ts = env.get("timestamp") or {}
    return {"manifest_id": row.id, "manifest_sha256": row.manifest_sha256, "key_id": row.key_id, "signed_at": row.created_at.isoformat() + "Z",
            "rfc3161_gen_time": ts.get("gen_time"), "note": "Verify with the published public key; the case may have changed since signing."}

@router.post("/{incident_id}/evidence/bsa63-certificate")  # POST: it records a generated certificate row
def bsa_certificate(incident_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user),format:str=Query("json",pattern="^(json|text)$")):
    inc=_get_owned_incident(incident_id,db,current_user)
    media=db.query(MediaItem).filter(MediaItem.incident_id==inc.id).all(); evidence=db.query(EvidenceItem).filter(EvidenceItem.incident_id==inc.id).all()
    records=[{"record_type":"media","id":m.id,"filename":m.original_filename,"sha256":m.sha256,"captured_at":m.uploaded_at.isoformat()+"Z"} for m in media]
    records += [{"record_type":"evidence","id":e.id,"item_type":e.item_type,"sha256":e.sha256,"captured_at":e.captured_at.isoformat()+"Z"} for e in evidence]
    payload={"template":"BSA Section 63 electronic-record certificate draft","template_version":settings.BSA_CERTIFICATE_TEMPLATE_VERSION,"act":"Bharatiya Sakshya Adhiniyam, 2023","section":"63","incident_id":inc.id,"records":records,"device_particulars":{"application":"LINEAGE","runtime":platform.platform()},"production_description":"Electronic records preserved by LINEAGE with SHA-256 hashes and encrypted-at-rest storage; complete system/device particulars and statutory declarations must be completed and reviewed by qualified counsel before use.","conditions_checklist":["regularly used system/process","ordinary-course information input","system operation and integrity","record derived from ordinary-course information"],"signer":{"name":"","designation":"","date":""},"legal_status":legal_status_text(),"integrity_manifest":latest_manifest_reference(db,inc.id)}
    row=EvidenceCertificate(incident_id=inc.id,generated_by=current_user.id,template_version=settings.BSA_CERTIFICATE_TEMPLATE_VERSION,certificate_json=json.dumps(payload,default=str)); db.add(row); audit.record(db,inc.id,current_user,"evidence_certificate_generated",target_type="certificate",target_id=row.id,commit=False); db.commit()
    if format=="text": return Response(content=json.dumps(payload,indent=2),media_type="text/plain")
    return payload

@router.get("/{incident_id}/trust/status")
def trust_status(incident_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    _get_owned_incident(incident_id,db,current_user)
    return {"legal_review":settings.LEGAL_REVIEW_STATUS,"privacy_policy_version":settings.PRIVACY_POLICY_VERSION,"bsa_certificate_template":settings.BSA_CERTIFICATE_TEMPLATE_VERSION,"victim_support_url":settings.VICTIM_SUPPORT_URL,"support_email":settings.SUPPORT_EMAIL or None,"note":"Legal review status is configuration, not a representation that counsel has approved the product."}

@router.get("/{incident_id}/victim-support")
def victim_support(incident_id,db:Session=Depends(get_db),current_user:User=Depends(get_current_user)):
    _get_owned_incident(incident_id,db,current_user)
    return {"resources":[{"name":"National Cyber Crime Reporting Portal","url":settings.VICTIM_SUPPORT_URL,"description":"Use the official portal for reporting cybercrime in India."}],"safety":"If opening this page could expose you to risk, use a safer device/account and follow your local support organisation's guidance.","note":"LINEAGE does not contact authorities or platforms automatically."}
