"""RFC 6238 TOTP (SHA-1, 6 digits, 30 s) with no third-party dependency."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote


def new_secret(nbytes: int = 20) -> str:
    return base64.b32encode(secrets.token_bytes(nbytes)).decode().rstrip("=")


def _key(secret: str) -> bytes:
    s = secret.strip().replace(" ", "").upper()
    return base64.b32decode(s + "=" * (-len(s) % 8))


def hotp(secret: str, counter: int, digits: int = 6) -> str:
    mac = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    off = mac[-1] & 0x0F
    code = (struct.unpack(">I", mac[off:off + 4])[0] & 0x7FFFFFFF) % (10 ** digits)
    return str(code).zfill(digits)


def totp(secret: str, at: float | None = None, step: int = 30, digits: int = 6) -> str:
    return hotp(secret, int((time.time() if at is None else at) // step), digits)


def verify(secret: str, code: str, at: float | None = None, window: int = 1, step: int = 30) -> bool:
    """Constant-time check of `code` within +/- `window` steps."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return False
    now = int((time.time() if at is None else at) // step)
    ok = False
    for d in range(-window, window + 1):
        ok |= hmac.compare_digest(hotp(secret, now + d), code)
    return ok


def provisioning_uri(secret: str, account: str, issuer: str) -> str:
    return (f"otpauth://totp/{quote(issuer)}:{quote(account)}?secret={secret}"
            f"&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30")


def match_step(secret: str, code: str, at: float | None = None, window: int = 1, step: int = 30) -> int | None:
    """Return the time step the code belongs to (constant-time compare), or None. Callers store the step and refuse
    any step <= the last accepted one, so a code cannot be used twice."""
    code = (code or "").strip().replace(" ", "")
    if not code.isdigit() or len(code) != 6:
        return None
    now = int((time.time() if at is None else at) // step)
    found = None
    for d in range(-window, window + 1):
        if hmac.compare_digest(hotp(secret, now + d), code):
            found = now + d
    return found
