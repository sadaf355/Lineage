"""Phase 5 audit trail helper. Records WHO (the authenticated user), WHAT and WHEN. Never touches evidence rows."""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.automation import AuditEvent
from app.models.incident import Incident
from app.services import audit_chain

ACTIONS = (
    "report_generated", "legacy_report_generated", "evidence_reviewed", "finding_reviewed",
    "location_added", "location_edited", "location_deleted", "direction_confirmed", "direction_revoked",
    "alert_draft_generated", "alert_draft_edited", "alert_draft_approved", "alert_draft_exported",
    "investigation_exported", "status_changed", "source_trace_requested", "source_trace_match_reviewed", "integrity_verified", "media_deleted", "incident_deleted", "evidence_certificate_generated",
    "upload_rejected", "upload_unverified",
    # Previously written by endpoints but never registered here, which made those endpoints raise ValueError (HTTP 500).
    "reverse_search_requested", "retention_purge", "request_pack_generated", "evidence_deleted",
    # Phase E
    "manifest_signed", "manifest_verified",
    # Phase 2-4 additions
    "legal_pack_generated", "case_bundle_exported", "mfa_enabled", "mfa_disabled",
)


MAX_CHAIN_ATTEMPTS = 8


def _next_event(db: Session, incident_id: str, user, action: str, target_type, target_id, details) -> AuditEvent:
    """Build one event linked to the current head of this case's chain."""
    ev = AuditEvent(
        incident_id=incident_id, actor_user_id=getattr(user, "id", None), actor_email=getattr(user, "email", None),
        action=action, target_type=target_type, target_id=target_id,
        details_json=json.dumps(details, default=str) if details else None, created_at=datetime.utcnow(),
    )
    last = (db.query(AuditEvent).filter(AuditEvent.incident_id == incident_id, AuditEvent.seq.isnot(None))
            .order_by(AuditEvent.seq.desc()).first())
    ev.seq = (last.seq + 1) if last else 1
    ev.prev_hash = last.event_hash if last else audit_chain.GENESIS
    ev.event_hash = audit_chain.event_hash(chain_fields(ev), ev.prev_hash)
    return ev


def record(db: Session, incident_id: str, user, action: str, *, target_type: str | None = None,
           target_id: str | None = None, details: dict | None = None, commit: bool = True) -> AuditEvent:
    """`user` is the authenticated User (or None for a system event, which is then stored with no actor).

    Concurrency: two writers on one case must not both take the same `seq`. Three layers:
      1. the case row is locked (SELECT ... FOR UPDATE; honoured by PostgreSQL, ignored by SQLite), which serialises writers;
      2. a unique index on (incident_id, seq) makes a duplicate impossible even where locking does nothing (SQLite, no index lock);
      3. the insert runs in a SAVEPOINT, and on a unique-index conflict the event is rebuilt against the new head and retried.
    """
    if action not in ACTIONS:
        raise ValueError(f"Unknown audit action: {action}")
    if not get_settings().AUDIT_CHAIN_ENABLED:
        ev = AuditEvent(
            incident_id=incident_id, actor_user_id=getattr(user, "id", None), actor_email=getattr(user, "email", None),
            action=action, target_type=target_type, target_id=target_id,
            details_json=json.dumps(details, default=str) if details else None, created_at=datetime.utcnow(),
        )
        db.add(ev)
        if commit:
            db.commit()
        return ev
    ev = None
    for _ in range(MAX_CHAIN_ATTEMPTS):
        db.query(Incident.id).filter(Incident.id == incident_id).with_for_update().first()
        candidate = _next_event(db, incident_id, user, action, target_type, target_id, details)
        try:
            with db.begin_nested():
                db.add(candidate)
                db.flush()
            ev = candidate
            break
        except IntegrityError:
            continue          # someone else took this seq; the nested rollback already discarded `candidate`
    if ev is None:
        raise RuntimeError("Could not append to the audit chain after repeated conflicts.")
    if commit:
        db.commit()
    return ev


def chain_fields(ev: AuditEvent) -> dict:
    """The exact fields that are hashed. Used when writing and when verifying, so both always agree."""
    return {"incident_id": ev.incident_id, "seq": ev.seq, "actor_user_id": ev.actor_user_id, "actor_email": ev.actor_email,
            "action": ev.action, "target_type": ev.target_type, "target_id": ev.target_id, "details_json": ev.details_json,
            "created_at": ev.created_at}


def _chain_rows(db: Session, incident_id: str) -> list[dict]:
    rows = db.query(AuditEvent).filter(AuditEvent.incident_id == incident_id).order_by(AuditEvent.created_at).all()
    return [{**chain_fields(r), "prev_hash": r.prev_hash, "event_hash": r.event_hash} for r in rows]


def verify_chain(db: Session, incident_id: str) -> dict:
    return audit_chain.verify(_chain_rows(db, incident_id))


def anchor(db: Session, incident_id: str) -> dict | None:
    """Head of the chain as a small dict for a signed manifest or a bundle (see audit_chain.anchor)."""
    return audit_chain.anchor(verify_chain(db, incident_id))


def export_chain(db: Session, incident_id: str) -> list[dict]:
    """Raw chained fields for an offline re-check: audit_chain.verify() on this list reproduces verify_chain()."""
    return [audit_chain.export_row(r) for r in _chain_rows(db, incident_id)]


def to_dict(ev: AuditEvent) -> dict:
    return {
        "id": ev.id, "incident_id": ev.incident_id, "action": ev.action, "target_type": ev.target_type,
        "target_id": ev.target_id, "actor": {"user_id": ev.actor_user_id, "email": ev.actor_email} if ev.actor_user_id else None,
        "details": json.loads(ev.details_json) if ev.details_json else None,
        "created_at": ev.created_at.isoformat() + "Z" if ev.created_at else None,
        "seq": ev.seq, "event_hash": ev.event_hash,
    }


def list_events(db: Session, incident_id: str) -> list[dict]:
    rows = db.query(AuditEvent).filter(AuditEvent.incident_id == incident_id).order_by(AuditEvent.created_at).all()
    return [to_dict(r) for r in rows]
