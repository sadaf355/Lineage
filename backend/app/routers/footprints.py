from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.user import User
from app.models.media import MediaItem
from app.models.source import Source
from app.routers.incidents import _get_owned_incident
from app.services import file_storage, footprints

router = APIRouter(prefix="/incidents", tags=["footprints"])

@router.get("/{incident_id}/footprints")
def get_footprints(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inc = _get_owned_incident(incident_id, db, current_user)
    media_rows = db.query(MediaItem).filter(MediaItem.incident_id == inc.id).all()
    source_rows = db.query(Source).filter(Source.incident_id == inc.id).all()
    media = []
    for m in media_rows:
        try:
            media.append({"media_id": m.id, **footprints.media_metadata(file_storage.read_decrypted(m.storage_path), m.original_filename), "sha256": m.sha256})
        except Exception as exc:
            media.append({"media_id": m.id, "filename": m.original_filename, "sha256": m.sha256, "error": str(exc)})
    hosting = [footprints.hosting_footprint(s.url) for s in source_rows if s.url]
    return {"media": media, "hosting": hosting, "attribution_gap": "Creator IP or account identity: requires platform disclosure via a legal request."}
