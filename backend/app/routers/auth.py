from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_refresh_payload,
)
from app.db.session import get_db
from app.deps import get_current_user
from app.models.refresh_session import RefreshSession
from app.models.user import User
from app.services import mfa, redis_rate_limit, totp
from app.core.config import get_settings
from app.schemas.auth import UserCreate, UserOut, Token

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _client_ip(request: Request) -> str:
    # Do not trust X-Forwarded-For unless the deployment explicitly puts the
    # API behind a trusted proxy that sanitizes it. Starlette's peer address is
    # the safe default for the standalone app and Docker compose setup.
    return request.client.host if request.client else "unknown"


CSRF_HEADER = "x-lineage-csrf"


def require_csrf(request: Request) -> None:
    """Cookie-authenticated endpoints need a header a cross-site form or image cannot send,
    and, when the browser sends an Origin, it must be one of the configured app origins."""
    if request.headers.get(CSRF_HEADER) != "1":
        raise HTTPException(status_code=403, detail="Missing CSRF header")
    origin = request.headers.get("origin")
    if origin and origin not in settings.cors_origins_list:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def _issue_refresh_session(db: Session, user_id: str) -> str:
    token, jti = create_refresh_token(user_id)
    expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    db.add(RefreshSession(user_id=user_id, jti_hash=RefreshSession.hash_jti(jti), expires_at=expires_at))
    db.commit()
    return token


def _revoke_refresh_session(db: Session, token: str) -> bool:
    payload = decode_refresh_payload(token)
    if not payload:
        return False
    session = db.query(RefreshSession).filter(RefreshSession.jti_hash == RefreshSession.hash_jti(payload["jti"])).first()
    if not session or session.revoked_at is not None:
        return False
    session.revoked_at = datetime.utcnow()
    db.commit()
    return True


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: UserCreate, db: Session = Depends(get_db)):
    # Email addresses are canonicalized at the application boundary so login,
    # uniqueness checks, and existing-account lookup all use the same value.
    email = payload.email.strip().lower()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=400, detail="An account with this email already exists.")
    user = User(email=email, hashed_password=hash_password(payload.password), display_name=payload.display_name)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(response: Response, request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    email = (form_data.username or "anonymous").strip().lower()
    key = f"login:{_client_ip(request)}:{email}"
    if not redis_rate_limit.allow(key, settings.RATE_LIMIT_LOGIN_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please wait a minute before trying again.")
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    if getattr(user, "mfa_enabled", False):
        # Second factor in the X-Lineage-OTP header: a 6-digit code (each time step usable once) or a one-time recovery code.
        otp = request.headers.get("x-lineage-otp", "")
        if not otp:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="mfa_required", headers={"WWW-Authenticate": "Bearer"})
        res = mfa.check(mfa.decrypt_secret(user.mfa_secret), user.mfa_last_step, user.mfa_recovery_hashes, otp)
        if not res.ok:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="mfa_invalid", headers={"WWW-Authenticate": "Bearer"})
        if res.via == "totp":
            user.mfa_last_step = res.last_step
        else:
            user.mfa_recovery_hashes = res.recovery_json
        db.commit()
    token = create_access_token(subject=user.id)
    refresh = _issue_refresh_session(db, user.id)
    response.set_cookie("lineage_refresh", refresh, httponly=True, secure=settings.AUTH_COOKIE_SECURE,
                        samesite=settings.AUTH_COOKIE_SAMESITE, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/auth")
    return Token(access_token=token, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


class MfaCode(BaseModel):
    code: str


def _mfa_limit(user: User) -> None:
    if not redis_rate_limit.allow(f"mfa:{user.id}", settings.RATE_LIMIT_LOGIN_PER_MINUTE):
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a minute.")


def _verify_current(user: User, code: str, db: Session) -> bool:
    """Check a TOTP or recovery code for an enrolled user and record its use (replay and one-time rules)."""
    res = mfa.check(mfa.decrypt_secret(user.mfa_secret), user.mfa_last_step, user.mfa_recovery_hashes, code)
    if res.ok:
        if res.via == "totp":
            user.mfa_last_step = res.last_step
        else:
            user.mfa_recovery_hashes = res.recovery_json
        db.commit()
    return res.ok


@router.get("/mfa/status")
def mfa_status(current_user: User = Depends(get_current_user)):
    return {"enabled": bool(current_user.mfa_enabled), "required": settings.MFA_REQUIRED,
            "recovery_codes_remaining": mfa.remaining(current_user.mfa_recovery_hashes) if current_user.mfa_enabled else 0}


@router.post("/mfa/setup")
def mfa_setup(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create (or replace, while not yet enabled) a TOTP secret, stored encrypted. Returns the otpauth URI for an authenticator app."""
    if current_user.mfa_enabled:
        raise HTTPException(status_code=409, detail="MFA is already enabled. Disable it first to re-enrol.")
    secret = totp.new_secret()
    try:
        current_user.mfa_secret = mfa.encrypt_secret(secret)
    except mfa.MfaConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    current_user.mfa_last_step = None
    db.commit()
    return {"secret": secret, "otpauth_uri": totp.provisioning_uri(secret, current_user.email, settings.MFA_ISSUER)}


@router.post("/mfa/enable")
def mfa_enable(body: MfaCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Confirm the first code, switch MFA on and return ten one-time recovery codes. They are shown only this once."""
    _mfa_limit(current_user)
    secret = mfa.decrypt_secret(current_user.mfa_secret)
    if not secret:
        raise HTTPException(status_code=400, detail="Call /auth/mfa/setup first.")
    step = totp.match_step(secret, body.code)
    if step is None:
        raise HTTPException(status_code=400, detail="Code did not match. Check your device clock and try again.")
    codes = mfa.new_recovery_codes()
    current_user.mfa_enabled = True
    current_user.mfa_last_step = step
    current_user.mfa_recovery_hashes = mfa.hash_codes(codes)
    db.commit()
    return {"mfa_enabled": True, "recovery_codes": codes,
            "note": "Store these somewhere safe. Each works once if you lose your phone. They will not be shown again."}


@router.post("/mfa/recovery-codes")
def mfa_new_recovery_codes(body: MfaCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Replace all recovery codes (the old ones stop working). Needs a current authenticator code."""
    _mfa_limit(current_user)
    if not current_user.mfa_enabled or not _verify_current(current_user, body.code, db):
        raise HTTPException(status_code=400, detail="Code did not match.")
    codes = mfa.new_recovery_codes()
    current_user.mfa_recovery_hashes = mfa.hash_codes(codes)
    db.commit()
    return {"recovery_codes": codes}


@router.post("/mfa/disable")
def mfa_disable(body: MfaCode, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _mfa_limit(current_user)
    if settings.MFA_REQUIRED:
        raise HTTPException(status_code=409, detail="MFA is required on this deployment and cannot be turned off.")
    if not current_user.mfa_enabled or not _verify_current(current_user, body.code, db):
        raise HTTPException(status_code=400, detail="Code did not match.")
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.mfa_last_step = None
    current_user.mfa_recovery_hashes = None
    db.commit()
    return {"mfa_enabled": False}


@router.get("/me", response_model=UserOut)
def read_current_user(current_user: User = Depends(get_current_user)):
    out = UserOut.model_validate(current_user)
    out.mfa_setup_required = bool(settings.MFA_REQUIRED and not current_user.mfa_enabled)
    return out


@router.post("/refresh", response_model=Token)
def refresh(response: Response, request: Request, db: Session = Depends(get_db)):
    require_csrf(request)
    refresh_token = request.cookies.get("lineage_refresh")
    if not refresh_token:
        raise HTTPException(status_code=401, detail="No refresh session")
    payload = decode_refresh_payload(refresh_token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh session")
    session = db.query(RefreshSession).filter(
        RefreshSession.jti_hash == RefreshSession.hash_jti(payload["jti"]),
        RefreshSession.user_id == payload["sub"],
    ).first()
    if not session or session.revoked_at is not None or session.expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Refresh session has been revoked or expired")
    user = db.query(User).filter(User.id == payload["sub"], User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=401, detail="Account is inactive")
    session.revoked_at = datetime.utcnow()
    access = create_access_token(user.id)
    rotated = _issue_refresh_session(db, user.id)
    response.set_cookie("lineage_refresh", rotated, httponly=True, secure=settings.AUTH_COOKIE_SECURE,
                        samesite=settings.AUTH_COOKIE_SAMESITE, max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, path="/auth")
    db.commit()
    return Token(access_token=access, expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)


@router.post("/logout", status_code=204)
def logout(response: Response, request: Request, db: Session = Depends(get_db)):
    require_csrf(request)
    token = request.cookies.get("lineage_refresh")
    if token:
        _revoke_refresh_session(db, token)
    response.delete_cookie("lineage_refresh", path="/auth")
