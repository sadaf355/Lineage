import json
import mimetypes
import hashlib
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.deps import get_current_user
from app.models.incident import Incident
from app.models.media import MediaItem, DetectionResult, Fingerprint
from app.models.source import EvidenceItem, Source, UPLOAD_SOURCE_PLATFORM
from app.models.user import User
from app.schemas.media import MediaItemOut, DetectionResultOut, FingerprintOut
from app.services import file_storage, pixel_analysis, deepfake_model, face_embedding, exif_gps, model_explainability
from app.services import phase34
from app.services.integrity import verify_sha256
from app.models.location import SourceLocation
from app.routers.incidents import _get_owned_incident
from app.services.rate_limit import limiter
from app.services import redis_rate_limit
from app.services import audit
from app.services import metadata_snapshots
from app.models.media import MetadataSnapshot
from app.services.operations import record_operational_event
from app.services import upload_guard
from app.services.upload_sniff import safe_ext

router = APIRouter(prefix="/incidents", tags=["media"])
settings = get_settings()
log = logging.getLogger(__name__)

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
VIDEO_TYPES = {"video/mp4", "video/quicktime", "video/webm", "video/x-msvideo"}
AUDIO_TYPES = {"audio/mpeg", "audio/wav", "audio/x-wav", "audio/ogg", "audio/webm", "audio/mp4", "audio/x-m4a"}
UPLOAD_RELATIONSHIP_LABEL = "Submitted media; original posting location is unverified."


def _ensure_upload_evidence(incident: Incident, media: MediaItem, db: Session) -> bool:
    item_type = f"uploaded_{media.kind}"
    evidence = (
        db.query(EvidenceItem)
        .filter(
            EvidenceItem.incident_id == incident.id,
            EvidenceItem.storage_path == media.storage_path,
            EvidenceItem.item_type == item_type,
        )
        .first()
    )
    if evidence:
        return False

    observed_at = media.uploaded_at or datetime.utcnow()
    source = Source(
        incident_id=incident.id,
        platform=UPLOAD_SOURCE_PLATFORM,
        observed_at=observed_at,
        relationship_label=UPLOAD_RELATIONSHIP_LABEL,
        is_seeded=False,
    )
    db.add(source)
    db.flush()

    db.add(
        EvidenceItem(
            incident_id=incident.id,
            source_id=source.id,
            item_type=item_type,
            storage_path=media.storage_path,
            notes=(
                f"Original uploaded file: {media.original_filename}. "
                "Stored encrypted; external posting location has not been established."
            ),
        )
    )
    return True


def _get_media_item(incident_id: str, media_id: str, db: Session, user: User) -> MediaItem:
    incident = _get_owned_incident(incident_id, db, user)
    media = (
        db.query(MediaItem)
        .filter(MediaItem.id == media_id, MediaItem.incident_id == incident.id)
        .first()
    )
    if not media:
        raise HTTPException(status_code=404, detail="Media item not found.")
    return media


@router.get("/{incident_id}/media", response_model=list[MediaItemOut])
def list_media(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    items = (
        db.query(MediaItem)
        .filter(MediaItem.incident_id == incident.id)
        .order_by(MediaItem.uploaded_at)
        .all()
    )
    changed = False
    for item in items:
        changed = _ensure_upload_evidence(incident, item, db) or changed
    if changed:
        db.commit()
    return items


@router.post("/{incident_id}/media", response_model=MediaItemOut, status_code=201)
async def upload_media(
    incident_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    if not redis_rate_limit.allow(f"upload:{current_user.id}", settings.RATE_LIMIT_UPLOAD_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Upload rate limit reached. Please wait a minute before uploading more files.")

    content_type = file.content_type or ""
    if content_type in IMAGE_TYPES:
        kind = "image"
    elif content_type in VIDEO_TYPES:
        kind = "video"
    elif content_type in AUDIO_TYPES:
        kind = "audio"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported content type '{content_type}'. Upload an image, video, or audio file.",
        )

    # Do not trust the declared Content-Type or filename: check the real bytes before anything is stored.
    try:
        upload_guard.guard_media_upload(db, incident.id, current_user, file.file, file.filename, kind)
        upload_guard.scan_upload(db, incident.id, current_user, file.file, file.filename, kind)
    except HTTPException as exc:
        category = "scan_failure" if "scanner" in str(exc.detail).lower() or "scan" in str(exc.detail).lower() else "upload_refusal"
        record_operational_event(db, category, f"http_{exc.status_code}:{exc.detail}", current_user.id)
        db.commit()
        raise

    max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
    try:
        storage_path, size, sha256 = file_storage.save_encrypted_stream(file.file, file.filename or "upload", max_bytes)
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Could not securely store the upload: {exc}")

    # Analyze from a temporary decrypted file. New LINEAGE2 uploads are
    # decrypted chunk-by-chunk, so this avoids a second whole-file plaintext
    # allocation just to inspect dimensions/GPS.
    temp_suffix = safe_ext(file.filename)
    try:
        with file_storage.decrypted_tempfile(storage_path, suffix=temp_suffix) as temp_path:
            if kind == "image":
                from PIL import Image
                from app.services.upload_limits import validate_image_limits
                # Read dimensions from headers before pixel decoding or ML analysis.
                with Image.open(temp_path) as header_image:
                    validate_image_limits(header_image.width, header_image.height, size, settings)
                    width, height = header_image.width, header_image.height
                result = pixel_analysis.analyze_image_file(temp_path, file_size_bytes=size)
                gps = exif_gps.extract_gps_file(temp_path)
            elif kind == "video":
                from app.services.upload_limits import validate_video_limits
                # Probe frame count and duration before the analysis pipeline decodes frames.
                from app.services.upload_limits import VideoProbeUnavailable
                try:
                    validate_video_limits(temp_path, size, settings)
                except VideoProbeUnavailable as exc:
                    if settings.UPLOAD_SNIFF_STRICT_AV:
                        raise
                    record_operational_event(db, "upload_unverified", "video_limits_unverified", current_user.id)
                    audit.record(db, incident.id, current_user, "upload_limits_unverified", target_type="media",
                                 details={"reason": str(exc), "note": "frame and duration limits could not be checked"}, commit=False)
                result = pixel_analysis.analyze_video_file(temp_path, suffix=temp_suffix or ".mp4")
                width, height = result.width, result.height
                gps = None
            else:
                width = height = None
                gps = None
    except ValueError as exc:
        record_operational_event(db, "upload_refusal", str(exc), current_user.id)
        audit.record(db, incident.id, current_user, "upload_rejected", target_type="media", details={"reason": str(exc)})
        try: file_storage.delete_encrypted(storage_path)
        except Exception: pass
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception as exc:
        # Analysis failure must be observable. Storing the upload without
        # dimensions is acceptable; silently swallowing the exception is not.
        log.exception("Upload analysis failed for incident=%s filename=%s", incident.id, file.filename)
        record_operational_event(db, "scan_failure", f"upload_analysis_failed:{type(exc).__name__}", current_user.id)
        width, height, gps = None, None, None

    media = MediaItem(
        incident_id=incident.id,
        kind=kind,
        original_filename=file.filename or "upload",
        storage_path=storage_path,
        file_size_bytes=size,
        sha256=sha256,
        width=width,
        height=height,
    )
    db.add(media)
    db.flush()
    _ensure_upload_evidence(incident, media, db)
    # Preserve immutable metadata at ingest, tied to the original SHA-256.
    try:
        # Only the first 4 MB is parsed (the parser never reads past that), so large files are not loaded whole.
        with file_storage.decrypted_tempfile(storage_path) as plain_path:
            with open(plain_path, "rb") as plain:
                header_bytes = plain.read(4 * 1024 * 1024)
        metadata_snapshots.create_snapshot(db, media, header_bytes)
    except Exception as exc:
        log.exception("Metadata snapshot failed for media=%s", media.id)
        db.rollback()  # drop the half-added media row, then keep the counter
        record_operational_event(db, "scan_failure", "metadata_snapshot_failed", current_user.id)
        db.commit()
        try: file_storage.delete_encrypted(storage_path)
        except Exception: pass
        raise HTTPException(status_code=422, detail="Could not create the required metadata snapshot; upload was not accepted.")

    # Real EXIF GPS -> verified-tier location on the upload source (Phase 1 map).
    # Only recorded when the file actually carries a GPS block; never guessed.
    if kind == "image" and gps:
            db.flush()
            ev = (
                db.query(EvidenceItem)
                .filter(EvidenceItem.incident_id == incident.id, EvidenceItem.storage_path == media.storage_path)
                .first()
            )
            if ev and ev.source_id:
                db.add(SourceLocation(
                    source_id=ev.source_id,
                    latitude=gps["latitude"],
                    longitude=gps["longitude"],
                    place_name=None,
                    provenance="exif_gps",
                    confidence=90.0,
                    basis=f"GPS block read from EXIF metadata of uploaded file '{media.original_filename}'. "
                          "EXIF can be edited or stripped; treat as metadata-derived, not proof of capture location.",
                    evidence_item_id=ev.id,
                    recorded_by="system:exif",
                ))

    if incident.status == "created":
        incident.status = "analyzing"

    db.commit()
    db.refresh(media)
    return media


@router.get("/{incident_id}/media/{media_id}/file")
def preview_media_file(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the authenticated original in an inline-safe media response."""
    media = _get_media_item(incident_id, media_id, db, current_user)
    raw = file_storage.read_decrypted(media.storage_path)
    media_type = mimetypes.guess_type(media.original_filename)[0]
    if not media_type:
        media_type = "video/mp4" if media.kind == "video" else "image/jpeg"
    return Response(
        content=raw,
        media_type=media_type,
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/{incident_id}/media/{media_id}/analysis-frame")
def preview_analysis_frame(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return the same still image or video key frame used by detection."""
    media = _get_media_item(incident_id, media_id, db, current_user)
    raw = file_storage.read_decrypted(media.storage_path)
    if media.kind == "video":
        try:
            suffix = Path(media.original_filename).suffix or ".mp4"
            raw = pixel_analysis.extract_video_frame_jpeg(raw, suffix=suffix)
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Could not extract the analysis frame: {e}")
        media_type = "image/jpeg"
    else:
        media_type = mimetypes.guess_type(media.original_filename)[0] or "image/jpeg"
    return Response(
        content=raw,
        media_type=media_type,
        headers={"Content-Disposition": "inline", "X-Content-Type-Options": "nosniff"},
    )


@router.post("/{incident_id}/media/{media_id}/detect", response_model=DetectionResultOut)
def run_detection(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = _get_media_item(incident_id, media_id, db, current_user)
    raw = file_storage.read_decrypted(media.storage_path)
    if media.kind == "audio":
        raise HTTPException(status_code=422, detail="Use /audio-analysis for audio. Audio deepfake detection is optional and only enabled when a validated model is configured.")

    # Try the real pretrained model first (TRD §5.1). Only images are
    # supported by the classifier directly; for video we run it against the
    # same mid-clip frame the heuristic/fingerprint pipeline already uses.
    frame_samples: list[tuple[bytes, float | None]] = []
    if media.kind == "image":
        frame_samples = [(raw, None)]
    else:
        try:
            suffix = Path(media.original_filename).suffix or ".mp4"
            frame_samples = [(b, ts) for b, ts in pixel_analysis.extract_video_frames_jpeg(raw, suffix=suffix, count=settings.DETECTOR_VIDEO_FRAME_COUNT)]
        except Exception:
            frame_samples = []
    frame_bytes = frame_samples[0][0] if frame_samples else None

    model_results = [deepfake_model.classify_image(b) for b, _ in frame_samples] if frame_samples else []
    ensemble_scores = []
    second_model_outputs = []
    if settings.DETECTOR_SECOND_MODEL_ID:
        for b, _ in frame_samples:
            try:
                result = phase34.ensemble_image_classification(b)
                second_model_outputs.append(result)
                if result.get("combined_score") is not None:
                    ensemble_scores.append(float(result["combined_score"]))
            except Exception:
                continue
    # Use the configured ensemble only when two actual models produced scores; otherwise use the primary detector.
    model_result = next((r for r in model_results if r.used_real_model and r.manipulation_likelihood is not None), model_results[0] if model_results else None)

    try:
        if media.kind == "audio":
            from app.services.phase34 import audio_spectrogram_fingerprint, audio_deepfake_score, extract_audio_wav
            wav = raw if media.original_filename.lower().endswith(".wav") else extract_audio_wav(raw, Path(media.original_filename).suffix)
            analysis = None
            audio_fp = audio_spectrogram_fingerprint(wav)
            audio_info = audio_deepfake_score(wav)
            face_embedding_json = json.dumps({"audio_detection": audio_info})
            face_bytes = None
        elif media.kind == "image":
            heuristic = pixel_analysis.analyze_image_bytes(raw)
        else:
            heuristic = pixel_analysis.analyze_video_bytes(raw, suffix=Path(media.original_filename).suffix or ".mp4")
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not analyze this file: {e}")

    real_scores = [r.manipulation_likelihood for r in model_results if r.used_real_model and r.manipulation_likelihood is not None]
    if ensemble_scores and settings.DETECTOR_SECOND_MODEL_ID:
        manipulation_likelihood = round(sum(ensemble_scores) / len(ensemble_scores), 2)
        model_name = f"two-model ensemble ({settings.DETECTOR_MODEL_ID} + {settings.DETECTOR_SECOND_MODEL_ID})"
        # Label which model produced which score, so the number is never anonymous.
        per_model: dict[str, list[float]] = {}
        for out in second_model_outputs:
            for ms in out.get("scores", []):
                if ms.get("loaded") and ms.get("score") is not None:
                    per_model.setdefault(ms["model_id"], []).append(float(ms["score"]))
        per_model_text = "; ".join(f"{mid}: {sum(v) / len(v):.1f}%" for mid, v in per_model.items())
        explanation = (f"Two configured image detectors were combined across {len(ensemble_scores)} sampled frame(s). "
                       f"Mean manipulation likelihood is {manipulation_likelihood}%. "
                       f"Frame confidence range: {min(ensemble_scores):.0f}–{max(ensemble_scores):.0f}%. "
                       f"Per-model mean: {per_model_text or 'unavailable'}.")
    elif real_scores:
        manipulation_likelihood = round(sum(real_scores) / len(real_scores), 2)
        model_name = model_result.model_id if model_result else "pretrained-detector"
        plural = "s" if len(real_scores) != 1 else ""
        band = f" Confidence band across {len(real_scores)} frame{plural}: {min(real_scores):.0f}–{max(real_scores):.0f}%."
        explanation = (
            f"Real pretrained model ({model_name}) scored {len(real_scores)} sampled frame{plural}; "
            f"mean manipulation likelihood is {manipulation_likelihood}%." + band
        )
    else:
        # Honest fallback — never presented as the real model's output.
        manipulation_likelihood = heuristic.signal_score
        model_name = "pixel-heuristic-v1 (fallback — real model unavailable)"
        reason = model_result.load_error if model_result else "media type not supported by the classifier"
        explanation = (
            f"Real detection model unavailable ({reason}); fell back to a pixel heuristic combining "
            f"edge-energy irregularity ({heuristic.edge_irregularity}%) and compression-density anomaly "
            f"({heuristic.compression_density}%). This heuristic is not a trained deepfake classifier — "
            f"see TRD §5.1."
        )

    explainability = None
    try:
        face_box = None
        face_confidence = None
        face_status = "not_detected"
        if frame_bytes:
            face_result = face_embedding.detect_face_region_from_bytes(frame_bytes)
            if face_result.found_face:
                face_status = "detected"
                face_box = face_result.box
                face_confidence = face_result.detection_confidence
            explainability = model_explainability.generate_occlusion_sensitivity(
                raw_bytes=frame_bytes,
                model_result=model_result,
                face_box=face_box,
                face_confidence=face_confidence,
                face_status=face_status,
                frame_timestamp_sec=getattr(heuristic, "frame_timestamp_sec", None),
            )
        else:
            explainability = model_explainability.generate_occlusion_sensitivity(
                raw_bytes=b"",
                model_result=model_result,
                face_box=None,
                face_confidence=None,
                face_status="not_detected",
                frame_timestamp_sec=getattr(heuristic, "frame_timestamp_sec", None),
            )
    except Exception as exc:
        explainability = {
            "status": "unavailable",
            "method": "blur-occlusion-sensitivity-v1",
            "message": f"Heatmap generation was unavailable ({type(exc).__name__}: {exc}).",
            "face_box": None,
            "face_confidence": None,
            "grid": None,
            "frame_timestamp_sec": getattr(heuristic, "frame_timestamp_sec", None),
        }

    if explainability and explainability.get("status") == "available":
        explanation = f"{explanation} Explainability: {explainability.get('message', 'Heatmap available.')}"

    existing = db.query(DetectionResult).filter(DetectionResult.media_item_id == media.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    detection = DetectionResult(
        media_item_id=media.id,
        manipulation_likelihood=manipulation_likelihood,
        edge_irregularity=heuristic.edge_irregularity,
        compression_density=heuristic.compression_density,
        detected_region=None,
        likely_technique=None,
        model_name=model_name,
        explanation=explanation,
        explainability_json=json.dumps(
            {**(explainability or {}), **({"ensemble": second_model_outputs} if second_model_outputs else {})}
        ),
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)
    return detection


@router.post("/{incident_id}/media/{media_id}/fingerprint", response_model=FingerprintOut)
def run_fingerprint(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    media = _get_media_item(incident_id, media_id, db, current_user)
    raw = file_storage.read_decrypted(media.storage_path)

    audio_fp = None
    audio_info = None
    try:
        if media.kind == "audio":
            from app.services.phase34 import audio_spectrogram_fingerprint, audio_deepfake_score, extract_audio_wav
            wav = raw if media.original_filename.lower().endswith(".wav") else extract_audio_wav(raw, Path(media.original_filename).suffix)
            audio_fp = audio_spectrogram_fingerprint(wav)
            audio_info = audio_deepfake_score(wav)
            face_bytes = None
            analysis = None
        elif media.kind == "image":
            analysis = pixel_analysis.analyze_image_bytes(raw)
            face_bytes = raw
        else:
            suffix = Path(media.original_filename).suffix or ".mp4"
            analysis = pixel_analysis.analyze_video_bytes(raw, suffix=suffix)
            face_bytes = pixel_analysis.extract_video_frame_jpeg(raw, suffix=suffix)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Could not analyze this file: {e}")

    # Real face embedding (TRD §5.2) — closes the gap the frontend prototype
    # explicitly could not: "computing a real face embedding needs a trained
    # model, which this no-backend prototype doesn't run."
    try:
        if face_bytes is None:
            face_embedding_json = json.dumps({"found_face": False, "note": "Audio media has no face embedding."})
        else:
            face_result = face_embedding.extract_face_embedding_from_bytes(face_bytes)
            face_embedding_json = face_embedding.embedding_to_json(face_result)
    except Exception as e:
        face_embedding_json = json.dumps({"found_face": False, "error": str(e)})

    existing = db.query(Fingerprint).filter(Fingerprint.media_item_id == media.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    fingerprint = Fingerprint(
        media_item_id=media.id,
        average_hash=analysis.average_hash if analysis else hashlib.sha256(raw).hexdigest()[:16],
        perceptual_hash=getattr(analysis, "perceptual_hash", None) if analysis else None,
        difference_hash=getattr(analysis, "difference_hash", None) if analysis else None,
        face_embedding_json=face_embedding_json,
        keyframe_hashes_json=json.dumps(
            [{"frame_sec": analysis.frame_timestamp_sec, "hash": analysis.average_hash}]
        ) if analysis and analysis.frame_timestamp_sec is not None else None,
        audio_fingerprint=audio_fp,
    )
    db.add(fingerprint)
    incident.status = "fingerprinted"
    db.commit()
    db.refresh(fingerprint)
    return fingerprint


@router.get("/{incident_id}/media/{media_id}/detection", response_model=DetectionResultOut)
def get_detection(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = _get_media_item(incident_id, media_id, db, current_user)
    if not media.detection_result:
        raise HTTPException(status_code=404, detail="No detection result yet — run /detect first.")
    return media.detection_result


@router.get("/{incident_id}/media/{media_id}/fingerprint", response_model=FingerprintOut)
def get_fingerprint(
    incident_id: str,
    media_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    media = _get_media_item(incident_id, media_id, db, current_user)
    if not media.fingerprint:
        raise HTTPException(status_code=404, detail="No fingerprint yet — run /fingerprint first.")
    return media.fingerprint


@router.get("/{incident_id}/media/{media_id}/integrity")
def verify_media_integrity(
    incident_id: str, media_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    media = _get_media_item(incident_id, media_id, db, current_user)
    raw = file_storage.read_decrypted(media.storage_path)
    verified, actual = verify_sha256(raw, media.sha256)
    audit.record(db, incident_id, current_user, "integrity_verified", target_type="media", target_id=media.id,
                 details={"stored_sha256": media.sha256, "actual_sha256": actual, "verified": verified})
    return {"verified": verified, "stored_sha256": media.sha256, "actual_sha256": actual, "filename": media.original_filename}


@router.delete("/{incident_id}/media/{media_id}", status_code=204)
def delete_media(
    incident_id: str, media_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user),
):
    media = _get_media_item(incident_id, media_id, db, current_user)
    incident = _get_owned_incident(incident_id, db, current_user)
    path = media.storage_path
    filename = media.original_filename
    audit.record(db, incident.id, current_user, "media_deleted", target_type="media", target_id=media_id, details={"filename": filename}, commit=False)
    db.delete(media)
    db.commit()
    try:
        file_storage.delete_encrypted(path)
    except Exception:
        pass
    return Response(status_code=204)
