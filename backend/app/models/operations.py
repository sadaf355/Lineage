from datetime import datetime
from sqlalchemy import Column, String, DateTime, Text, Integer
from app.db.session import Base
from app.models.user import gen_uuid

class CaseTombstone(Base):
    __tablename__ = "case_tombstones"
    id = Column(String, primary_key=True, default=gen_uuid)
    case_id = Column(String, unique=True, nullable=False, index=True)
    owner_user_id = Column(String, nullable=True, index=True)
    final_audit_head_hash = Column(String, nullable=True)
    deletion_event_json = Column(Text, nullable=False)
    deleted_at = Column(DateTime, default=datetime.utcnow, nullable=False)

class OperationalEvent(Base):
    __tablename__ = "operational_events"
    id = Column(String, primary_key=True, default=gen_uuid)
    category = Column(String, nullable=False, index=True)
    reason = Column(String, nullable=False)
    actor_user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
