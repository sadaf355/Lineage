from __future__ import annotations
from datetime import datetime, timedelta
from app.core.config import get_settings
from app.models.incident import Incident
from app.routers.incidents import _delete_incident_record
settings=get_settings()

def purge_expired_cases(db):
    cutoff=datetime.utcnow()-timedelta(days=settings.DATA_RETENTION_DAYS)
    rows=db.query(Incident).filter(Incident.created_at < cutoff).all()
    ids=[]
    for inc in rows:
        ids.append(inc.id); _delete_incident_record(inc,db)
    return {"deleted":len(ids),"incident_ids":ids,"cutoff":cutoff.isoformat()+"Z"}
