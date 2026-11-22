"""AES-256-GCM envelope encryption helper (per-case data key wrapped by a master key).

NOT wired into file_storage: stored files still use the existing Fernet encryption (FILE_ENCRYPTION_KEY). Nothing in the app
imports this module and there is deliberately no setting for it, so nobody mistakes it for a feature that is switched on.
It exists, with tests, for the day envelope encryption is adopted (see docs/YOUR_TODO.md).
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

VERSION = b"E1"


def master_key_from_b64(s: str) -> bytes:
    k = base64.b64decode(s)
    if len(k) != 32:
        raise ValueError("MASTER_KEY must be 32 bytes, base64 encoded")
    return k


def new_master_key_b64() -> str:
    return base64.b64encode(os.urandom(32)).decode()


def new_data_key() -> bytes:
    return AESGCM.generate_key(bit_length=256)


def wrap_key(master: bytes, data_key: bytes, context: str) -> bytes:
    n = os.urandom(12)
    return VERSION + n + AESGCM(master).encrypt(n, data_key, context.encode())


def unwrap_key(master: bytes, wrapped: bytes, context: str) -> bytes:
    if wrapped[:2] != VERSION:
        raise ValueError("unknown wrapped-key version")
    return AESGCM(master).decrypt(wrapped[2:14], wrapped[14:], context.encode())


def encrypt(data_key: bytes, plaintext: bytes, aad: str = "") -> bytes:
    n = os.urandom(12)
    return VERSION + n + AESGCM(data_key).encrypt(n, plaintext, aad.encode())


def decrypt(data_key: bytes, blob: bytes, aad: str = "") -> bytes:
    if blob[:2] != VERSION:
        raise ValueError("unknown ciphertext version")
    return AESGCM(data_key).decrypt(blob[2:14], blob[14:], aad.encode())
