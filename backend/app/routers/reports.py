import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.deps import get_current_user
from app.models.report import IncidentReport
from app.models.media import MediaItem
from app.models.source import EvidenceItem
from app.models.user import User
from app.schemas.report import IncidentReportOut, IncidentReportPayload
from app.services import audit, consent
from app.services.report_builder import build_report_payload
from app.services.report_pdf import render_report_pdf
from app.routers.incidents import _get_owned_incident

router = APIRouter(prefix="/incidents", tags=["report"])


def _to_out(report: IncidentReport) -> IncidentReportOut:
    return IncidentReportOut(
        id=report.id,
        incident_id=report.incident_id,
        generated_at=report.generated_at,
        payload=IncidentReportPayload(**json.loads(report.report_json)),
    )


@router.post("/{incident_id}/report", response_model=IncidentReportOut)
def generate_report(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    allow_llm = consent.has_granted_consent(db, incident.id, current_user.id, consent.PURPOSE_LLM)
    payload = build_report_payload(incident, db, allow_llm=allow_llm)

    existing = db.query(IncidentReport).filter(IncidentReport.incident_id == incident.id).first()
    if existing:
        db.delete(existing)
        db.flush()

    report = IncidentReport(incident_id=incident.id, report_json=payload.model_dump_json())
    db.add(report)
    incident.status = "report_generated"
    db.flush()
    audit.record(db, incident.id, current_user, "legacy_report_generated", target_type="report",  # Phase 5 audit trail
                 target_id=report.id, commit=False)
    db.commit()
    db.refresh(report)
    return _to_out(report)


@router.get("/{incident_id}/report", response_model=IncidentReportOut)
def get_report(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    incident = _get_owned_incident(incident_id, db, current_user)
    report = db.query(IncidentReport).filter(IncidentReport.incident_id == incident.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report yet — generate one first.")
    return _to_out(report)


@router.get("/{incident_id}/report/pdf")
def download_report_pdf(
    incident_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    language: str = Query("en", pattern="^(en|hi)$"),
):
    """Real PDF export — not the JSON re-served with a different content type."""
    incident = _get_owned_incident(incident_id, db, current_user)
    report = db.query(IncidentReport).filter(IncidentReport.incident_id == incident.id).first()
    if not report:
        raise HTTPException(status_code=404, detail="No report yet — generate one first.")

    payload = IncidentReportPayload(**json.loads(report.report_json))
    media_items = db.query(MediaItem).filter(MediaItem.incident_id == incident.id).all()
    evidence_items = db.query(EvidenceItem).filter(EvidenceItem.incident_id == incident.id).all()
    manifest = []
    for item in media_items:
        if item.sha256:
            manifest.append({"label": f"Media: {item.original_filename}", "sha256": item.sha256, "captured_at": item.uploaded_at.strftime("%Y-%m-%d %H:%M UTC")})
    for item in evidence_items:
        if item.sha256:
            manifest.append({"label": f"Evidence: {item.item_type}", "sha256": item.sha256, "captured_at": item.captured_at.strftime("%Y-%m-%d %H:%M UTC")})
    pdf_bytes = render_report_pdf(payload, incident.title, incident.id, manifest=manifest, language=language)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="incident-report-{incident.id[:8]}.pdf"'},
    )
