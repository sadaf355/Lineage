from __future__ import annotations

import csv
import io
import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.media import MediaItem
from app.models.user import User
from app.routers.incidents import _get_owned_incident
from app.services import audit, consent, eval_harness, file_storage, phase34, pixel_analysis, redis_rate_limit, source_tracing

router = APIRouter(prefix="/incidents", tags=["phase3-4"])
detector_router = APIRouter(prefix="/detection", tags=["detector-evaluation"])
settings = get_settings()


@detector_router.get("/evaluation/latest")
def latest_detector_evaluation(current_user: User = Depends(get_current_user)):
    """The last measured evaluation (written by backend/eval/run_eval.py), or an honest 'not run yet'.

    Account-level, not per case: the numbers describe the detector, not any investigation.
    """
    report = eval_harness.load_latest()
    return {
        "available": report is not None,
        # True when the test split is too small to quote (the UI must not show this as a measured result).
        "smoke_test": bool(report) and eval_harness.is_smoke_test(report),
        "report": report,
        "configured_models": {
            "primary": settings.DETECTOR_MODEL_ID,
            "second": settings.DETECTOR_SECOND_MODEL_ID or None,
            "ensemble_active": bool(settings.DETECTOR_SECOND_MODEL_ID),
        },
        "how_to_generate": None if report else "Run `python eval/run_eval.py` in backend/ (see backend/eval/README.md).",
    }


@router.get("/{incident_id}/detection/evaluation")
def detection_evaluation(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    return {"supported": True, "instructions": "Upload a labelled JSON manifest with label and score fields to /detection/evaluation/run.",
            "warning": "Metrics are only meaningful for the labelled set you supply; they are not a benchmark result."}


@router.post("/{incident_id}/detection/evaluation/run")
def run_detection_evaluation(incident_id: str, manifest: UploadFile = File(...), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    raw = awaitable_read(manifest)
    try:
        if manifest.filename and manifest.filename.lower().endswith(".csv"):
            rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8"))))
        else:
            rows = json.loads(raw.decode("utf-8"))
            if not isinstance(rows, list): raise ValueError("JSON manifest must be an array")
        return phase34.evaluate_binary_predictions(rows)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid evaluation manifest: {exc}")


def awaitable_read(upload: UploadFile) -> bytes:
    # FastAPI has already bounded multipart parsing at the reverse-proxy level in production.
    return upload.file.read()


@router.get("/{incident_id}/media/{media_id}/audio-analysis")
def audio_analysis(incident_id: str, media_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    media = db.query(MediaItem).filter(MediaItem.id == media_id, MediaItem.incident_id == incident_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    raw = file_storage.read_decrypted(media.storage_path)
    try:
        wav = raw if media.original_filename.lower().endswith(".wav") else phase34.extract_audio_wav(raw, Path(media.original_filename).suffix)
        fp = phase34.audio_spectrogram_fingerprint(wav)
        detection = phase34.audio_deepfake_score(wav)
        return {"fingerprint": fp, "deepfake_detection": detection,
                "note": "Audio fingerprinting is a provenance/matching signal; it is not an identity or authenticity verdict."}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/{incident_id}/media/{media_id}/reverse-search")
def reverse_search(incident_id: str, media_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    media = db.query(MediaItem).filter(MediaItem.id == media_id, MediaItem.incident_id == incident_id).first()
    if not media:
        raise HTTPException(status_code=404, detail="Media not found")
    if settings.REVERSE_SEARCH_PROVIDER == "google_vision":
        # The image itself is sent to a third party, so the investigator must have consented for this case.
        consent.require_consent(db, incident_id, current_user.id, consent.PURPOSE_REVERSE_SEARCH)
    raw = file_storage.read_decrypted(media.storage_path)
    result = phase34.licensed_reverse_image_search(raw)
    audit.record(db, incident_id, current_user, "reverse_search_requested", target_type="media", target_id=media_id, details={"provider": result.get("provider")}, commit=True)
    return result


@router.post("/{incident_id}/privacy/purge-retention")
def purge_retention(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    from datetime import datetime, timedelta
    from app.routers.incidents import _delete_incident_record
    incident = _get_owned_incident(incident_id, db, current_user)
    cutoff = datetime.utcnow() - timedelta(days=settings.DATA_RETENTION_DAYS)
    if incident.updated_at > cutoff:
        return {"deleted": False, "reason": "Case is newer than the configured retention period.", "retention_days": settings.DATA_RETENTION_DAYS}
    audit.record(db, incident.id, current_user, "retention_purge", target_type="incident", target_id=incident.id, details={"retention_days": settings.DATA_RETENTION_DAYS}, commit=True)
    _delete_incident_record(incident, db)
    return {"deleted": True, "retention_days": settings.DATA_RETENTION_DAYS}


@router.get("/{incident_id}/security/status")
def security_status(incident_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    _get_owned_incident(incident_id, db, current_user)
    return {"rate_limiting": redis_rate_limit.status(),
            "trace_limit_per_minute": settings.RATE_LIMIT_TRACE_PER_MINUTE,
            "copilot_limit_per_minute": settings.RATE_LIMIT_COPILOT_PER_MINUTE,
            "upload_limit_per_minute": settings.RATE_LIMIT_UPLOAD_PER_MINUTE,
            "access_token_minutes": settings.ACCESS_TOKEN_EXPIRE_MINUTES,
            "refresh_token_days": settings.REFRESH_TOKEN_EXPIRE_DAYS,
            "sensitive_action_review": settings.REQUIRE_REVIEW_FOR_SENSITIVE_ACTIONS,
            "data_retention_days": settings.DATA_RETENTION_DAYS,
            "key_provider": settings.KEY_PROVIDER,
            "key_rotation": {"supported": True, "previous_key_configured": bool(settings.FILE_ENCRYPTION_KEY_PREVIOUS.strip()), "secrets_manager_integration": "planned"}}
