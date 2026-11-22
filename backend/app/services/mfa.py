"""Second-factor logic: encrypted TOTP secrets, one-time recovery codes, replay protection.

Pure functions except `_cipher()` (reads settings). The router applies the returned changes to the User row.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from dataclasses import dataclass

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings
from app.services import totp

PREFIX = "enc1:"
_ALPHABET = "abcdefghjkmnpqrstuvwxyz23456789"        # no 0/1/i/l/o: easy to read out loud from paper


class MfaConfigError(RuntimeError):
    pass


def _dev() -> bool:
    return get_settings().ENV.lower() in {"development", "dev", "test"}


def _key_bytes() -> bytes:
    s = get_settings()
    k = (s.MFA_ENCRYPTION_KEY or "").strip()
    if k:
        return k.encode()
    if not _dev():
        raise MfaConfigError("MFA_ENCRYPTION_KEY must be set outside development/test (a Fernet key).")
    # Development only: derive a key from the JWT secret so local runs work without setup.
    return base64.urlsafe_b64encode(hashlib.sha256(("lineage-mfa|" + s.JWT_SECRET_KEY).encode()).digest())


def _cipher() -> Fernet:
    return Fernet(_key_bytes())


def encrypt_secret(plain: str) -> str:
    return PREFIX + _cipher().encrypt(plain.encode()).decode()


def decrypt_secret(stored: str | None) -> str | None:
    """Plaintext secret, or None if absent/unreadable. Values without the prefix are legacy plaintext and returned as is."""
    if not stored:
        return None
    if not stored.startswith(PREFIX):
        return stored
    try:
        return _cipher().decrypt(stored[len(PREFIX):].encode()).decode()
    except (InvalidToken, MfaConfigError):
        return None


def _norm_recovery(code: str) -> str:
    return "".join(ch for ch in (code or "").lower() if ch.isalnum())


def _hash_recovery(code: str) -> str:
    return hmac.new(_key_bytes(), b"recovery|" + _norm_recovery(code).encode(), hashlib.sha256).hexdigest()


def new_recovery_codes(n: int | None = None) -> list[str]:
    n = n or get_settings().MFA_RECOVERY_CODE_COUNT
    out = []
    for _ in range(n):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        out.append(f"{raw[:5]}-{raw[5:]}")
    return out


def hash_codes(codes: list[str]) -> str:
    return json.dumps([_hash_recovery(c) for c in codes])


def remaining(recovery_json: str | None) -> int:
    try:
        return len(json.loads(recovery_json or "[]"))
    except ValueError:
        return 0


@dataclass
class Check:
    ok: bool
    via: str | None = None                 # "totp" | "recovery"
    last_step: int | None = None           # store when via == "totp"
    recovery_json: str | None = None       # store when via == "recovery"


def check(secret_plain: str | None, last_step: int | None, recovery_json: str | None, code: str, at: float | None = None) -> Check:
    """Accept a fresh TOTP code (a time step later than the last one used) or an unused recovery code (consumed on use)."""
    code = (code or "").strip()
    if secret_plain:
        step = totp.match_step(secret_plain, code, at=at)
        if step is not None:
            if last_step is not None and step <= last_step:
                return Check(False)                   # replay of a code (or an older one) that was already accepted
            return Check(True, "totp", last_step=step)
    if len(_norm_recovery(code)) == 10 and not code.strip().isdigit():
        try:
            hashes = json.loads(recovery_json or "[]")
        except ValueError:
            hashes = []
        h = _hash_recovery(code)
        hit = None
        for x in hashes:
            if hmac.compare_digest(x, h):
                hit = x
        if hit is not None:
            hashes.remove(hit)
            return Check(True, "recovery", recovery_json=json.dumps(hashes))
    return Check(False)
