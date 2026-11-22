from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.phase56 import ConsentRecord

# Every purpose for which case data may leave this system. A purpose must be granted per investigation,
# by the investigator, before the matching outbound call is made. The latest record wins, so a later
# "granted: false" record revokes consent.
PURPOSE_WEB_SEARCH = "external_web_search"            # image sent to Google Gemini to draft search phrases
PURPOSE_LLM = "external_llm_processing"               # case facts sent to Anthropic (Copilot answers, report summary)
PURPOSE_REVERSE_SEARCH = "external_reverse_search"    # image sent to Google Cloud Vision web detection
KNOWN_PURPOSES = (PURPOSE_WEB_SEARCH, PURPOSE_LLM, PURPOSE_REVERSE_SEARCH)


def has_granted_consent(db: Session, incident_id: str, user_id: str, purpose: str) -> bool:
    row = (db.query(ConsentRecord)
           .filter(ConsentRecord.incident_id == incident_id,
                   ConsentRecord.user_id == user_id,
                   ConsentRecord.purpose == purpose)
           .order_by(ConsentRecord.created_at.desc()).first())
    return bool(row and row.granted)


def require_consent(db: Session, incident_id: str, user_id: str, purpose: str) -> None:
    """Raise HTTP 403 unless the investigator has granted `purpose` for this investigation."""
    if not has_granted_consent(db, incident_id, user_id, purpose):
        raise HTTPException(status_code=403, detail=f"Record {purpose} consent in the investigation privacy controls before using this feature.")
