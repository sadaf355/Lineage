import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Integer, Text
from sqlalchemy.orm import relationship

from app.db.session import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    """
    A minimal, real auth account. Deliberately thin — this is not meant to be
    a full identity system, just enough that every Incident is attached to a
    real, authenticated owner rather than being anonymous-by-default, per the
    TRD's requirement that even the hackathon build have an auth layer given
    the sensitivity of the data.
    """
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    display_name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    # Optional TOTP second factor. mfa_secret is set at /auth/mfa/setup and only trusted once mfa_enabled is True.
    mfa_secret = Column(String, nullable=True)
    mfa_enabled = Column(Boolean, default=False)
    mfa_last_step = Column(Integer, nullable=True)         # last accepted TOTP time step: a code cannot be reused
    mfa_recovery_hashes = Column(Text, nullable=True)       # JSON list of SHA-256 hashes of unused one-time recovery codes

    incidents = relationship("Incident", back_populates="owner", cascade="all, delete-orphan")
