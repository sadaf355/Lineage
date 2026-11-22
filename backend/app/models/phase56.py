from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, Boolean
from app.db.session import Base
from app.models.user import gen_uuid

class BackgroundJob(Base):
    __tablename__ = "background_jobs"
    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=True, index=True)
    owner_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    job_type = Column(String, nullable=False)
    payload_json = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="queued", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    error = Column(Text, nullable=True)
    result_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

class ConsentRecord(Base):
    __tablename__ = "consent_records"
    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    purpose = Column(String, nullable=False)
    policy_version = Column(String, nullable=False)
    granted = Column(Boolean, nullable=False)
    details_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class EvidenceCertificate(Base):
    __tablename__ = "evidence_certificates"
    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False, index=True)
    generated_by = Column(String, ForeignKey("users.id"), nullable=True)
    template_version = Column(String, nullable=False)
    certificate_json = Column(Text, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class SignedManifest(Base):
    """Phase E: an Ed25519-signed integrity manifest for a case, optionally RFC 3161 timestamped.

    The envelope is stored verbatim (manifest + signature + timestamp) so it can be exported and verified offline
    even if the case later changes. Rows are append-only: re-signing creates a new row, never edits an old one."""
    __tablename__ = "signed_manifests"
    id = Column(String, primary_key=True, default=gen_uuid)
    incident_id = Column(String, ForeignKey("incidents.id"), nullable=False, index=True)
    generated_by = Column(String, ForeignKey("users.id"), nullable=True)
    key_id = Column(String, nullable=False)
    manifest_sha256 = Column(String, nullable=False)
    envelope_json = Column(Text, nullable=False)
    has_timestamp = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
