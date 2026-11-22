from __future__ import annotations
import json, logging
from datetime import datetime
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.models.phase56 import BackgroundJob
from app.models.incident import Incident
from app.services import audit
log=logging.getLogger("lineage.jobs")
settings=get_settings()

def enqueue(db: Session, *, job_type: str, payload: dict, owner_id: str|None=None, incident_id: str|None=None) -> BackgroundJob:
    job=BackgroundJob(job_type=job_type,payload_json=json.dumps(payload),owner_id=owner_id,incident_id=incident_id)
    db.add(job); db.commit(); db.refresh(job)
    if settings.JOB_QUEUE_ENABLED and settings.REDIS_URL:
        try:
            import redis
            redis.Redis.from_url(settings.REDIS_URL, decode_responses=True).rpush("lineage:jobs", job.id)
        except Exception: log.exception("Could not enqueue Redis job; job remains persisted")
    return job

def run_job(db: Session, job: BackgroundJob) -> dict:
    job.status="running"; job.started_at=datetime.utcnow(); job.attempts += 1; db.commit()
    try:
        payload=json.loads(job.payload_json or "{}")
        if job.job_type == "retention_purge":
            from app.services.retention import purge_expired_cases
            result=purge_expired_cases(db)
        elif job.job_type == "capture_sweep":
            from app.services.capture_sweep import sweep_abandoned_captures
            result=sweep_abandoned_captures(db)
        elif job.job_type == "report":
            inc=db.query(Incident).filter(Incident.id==job.incident_id).first()
            if not inc: raise ValueError("Incident no longer exists")
            from app.models.automation import InvestigationReport
            from app.services import case_automation
            from sqlalchemy import func
            version=(db.query(func.max(InvestigationReport.version)).filter(InvestigationReport.incident_id==inc.id).scalar() or 0)+1
            rep=case_automation.build_report(inc,db,version=version)
            row=InvestigationReport(incident_id=inc.id,version=version,generated_by=job.owner_id,report_json=json.dumps(rep,default=str))
            db.add(row); db.flush(); result={"report_id":row.id,"version":version}
            if job.owner_id: audit.record(db,inc.id,db.get(__import__('app.models.user',fromlist=['User']).User,job.owner_id),"report_generated",target_type="report",target_id=row.id,details={"async_job":job.id},commit=False)
        else: raise ValueError(f"Unknown job type: {job.job_type}")
        job.status="succeeded"; job.result_json=json.dumps(result,default=str); job.finished_at=datetime.utcnow(); db.commit(); return result
    except Exception as exc:
        db.rollback(); job=db.get(BackgroundJob,job.id); job.status="failed"; job.error=f"{type(exc).__name__}: {exc}"; job.finished_at=datetime.utcnow(); db.commit(); log.exception("Background job failed: %s",job.id); raise
