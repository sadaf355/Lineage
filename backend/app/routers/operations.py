import json
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db.session import get_db
from app.deps import get_current_user
from app.core.config import get_settings
from app.models.user import User
from app.models.operations import OperationalEvent, CaseTombstone
router=APIRouter(tags=["operations"])
@router.get("/admin/operations/summary")
def operations_summary(db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    allowed={x.strip().lower() for x in get_settings().ADMIN_EMAILS.split(",") if x.strip()}
    if user.email.lower() not in allowed: raise HTTPException(status_code=403, detail="Administrator access required.")
    since=datetime.utcnow()-timedelta(days=30)
    rows=db.query(OperationalEvent.category, OperationalEvent.reason, func.count(OperationalEvent.id)).filter(OperationalEvent.created_at>=since).group_by(OperationalEvent.category, OperationalEvent.reason).all()
    return {"window_days":30,"counters":{f"{c}:{r}":n for c,r,n in rows}}
@router.get("/custody/tombstones/{case_id}")
def get_tombstone(case_id: str, db: Session=Depends(get_db), user: User=Depends(get_current_user)):
    row=db.query(CaseTombstone).filter(CaseTombstone.case_id==case_id).first()
    if not row or row.owner_user_id!=user.id: raise HTTPException(status_code=404, detail="No deletion tombstone found.")
    return {"case_id":row.case_id,"final_audit_head_hash":row.final_audit_head_hash,"deletion_event":json.loads(row.deletion_event_json),"deleted_at":row.deleted_at.isoformat()+"Z"}
