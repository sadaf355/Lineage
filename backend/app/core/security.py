from datetime import datetime, timedelta
from typing import Optional
import uuid

import bcrypt
try:
    from jose import jwt, JWTError
except ImportError:  # local test environments may provide PyJWT instead
    import jwt as _pyjwt
    from jwt import PyJWTError as JWTError

    class _JWTCompat:
        @staticmethod
        def encode(payload, key, algorithm):
            return _pyjwt.encode(payload, key, algorithm=algorithm)

        @staticmethod
        def decode(token, key, algorithms):
            return _pyjwt.decode(token, key, algorithms=algorithms)

    jwt = _JWTCompat()

from app.core.config import get_settings

settings = get_settings()

if settings.ENV.lower() not in {"development", "dev", "test"} and settings.JWT_SECRET_KEY in {"dev-only-secret-change-me", "change-me-before-any-real-deployment", ""}:
    raise RuntimeError("JWT_SECRET_KEY must be changed outside development/test environments.")


def hash_password(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]
    try:
        return bcrypt.checkpw(pw_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(subject: str, expires_minutes: Optional[int] = None) -> str:
    expire = datetime.utcnow() + timedelta(minutes=expires_minutes or settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode = {"sub": subject, "exp": expire, "typ": "access"}
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str, jti: str | None = None) -> tuple[str, str]:
    token_jti = jti or uuid.uuid4().hex
    expire = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = jwt.encode(
        {"sub": subject, "exp": expire, "typ": "refresh", "jti": token_jti},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )
    return token, token_jti


def decode_token(token: str, expected_type: str = "access") -> Optional[str]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("typ", "access") != expected_type:
            return None
        return payload.get("sub")
    except JWTError:
        return None


def decode_refresh_payload(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        if payload.get("typ") != "refresh" or not payload.get("sub") or not payload.get("jti"):
            return None
        return payload
    except JWTError:
        return None


def decode_access_token(token: str) -> Optional[str]:
    return decode_token(token, "access")
